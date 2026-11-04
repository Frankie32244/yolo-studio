import asyncio
import json
import logging
import math
import os
import shutil
import subprocess
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import imageio_ffmpeg
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine import DEVICE, MODEL_NAME, detector, read_image

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv("YOLO_DATA_DIR", str(ROOT / "data"))).resolve()
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "200")) * 1024 * 1024
MAX_VIDEO_SECONDS = int(os.getenv("MAX_VIDEO_SECONDS", "300"))
MAX_JOBS = int(os.getenv("MAX_JOBS", "100"))
JOBS = {}
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo")
SLOTS = threading.BoundedSemaphore(4)
log = logging.getLogger("yolo-web")


def persist(job):
    folder = DATA / job["id"]
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "job.json"
    temp = folder / "job.tmp"
    temp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def update(job_id, **changes):
    with LOCK:
        JOBS[job_id].update(changes)
        persist(JOBS[job_id])


@asynccontextmanager
async def lifespan(app):
    DATA.mkdir(parents=True, exist_ok=True)
    for path in DATA.glob("*/job.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            if job["status"] in ("uploading", "queued", "running"):
                job.update(status="failed", error="服务已重启，请重新提交任务")
                persist(job)
                (path.parent / job.get("input_file", "input")).unlink(missing_ok=True)
            JOBS[job["id"]] = job
        except (ValueError, KeyError, OSError):
            log.exception("Cannot restore %s", path)
    yield
    await asyncio.to_thread(POOL.shutdown, wait=True)


app = FastAPI(title="YOLO Studio API", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok", "model": Path(MODEL_NAME).name, "device": DEVICE,
            "model_loaded": detector._model is not None,
            "max_upload_mb": MAX_BYTES // (1024 * 1024),
            "max_video_seconds": MAX_VIDEO_SECONDS}


@app.get("/api/jobs")
def list_jobs():
    with LOCK:
        return sorted((dict(j) for j in JOBS.values()), key=lambda j: j["created_at"], reverse=True)


def get_job(job_id):
    with LOCK:
        if job_id not in JOBS:
            raise HTTPException(404, "任务不存在")
        return dict(JOBS[job_id])


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    return get_job(job_id)


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    with LOCK:
        job = get_job(job_id)
        if job["status"] in ("queued", "running"):
            raise HTTPException(409, "任务正在处理中，完成后可删除")
        shutil.rmtree(DATA / job_id, ignore_errors=True)
        del JOBS[job_id]


@app.post("/api/jobs", status_code=202)
async def create_job(file: UploadFile = File(...), confidence: float = Form(0.25, ge=0.01, le=1),
                     iou: float = Form(0.45, ge=0.01, le=1)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        await file.close()
        raise HTTPException(415, "不支持此文件格式")
    if not SLOTS.acquire(blocking=False):
        await file.close()
        raise HTTPException(429, "处理队列已满，请稍后重试")
    job_id = uuid.uuid4().hex
    folder = DATA / job_id
    reserved = False
    submitted = False
    try:
        # Reserve capacity before yielding to another upload request.
        with LOCK:
            if len(JOBS) >= MAX_JOBS:
                raise HTTPException(507, "任务存储已满，请删除旧任务后重试")
            job = {"id": job_id, "filename": Path(file.filename).name,
                   "kind": "image" if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp"} else "video",
                   "status": "uploading", "created_at": time.time(), "progress": 0,
                   "processed_frames": 0, "total_frames": 0, "confidence": confidence,
                   "iou": iou, "model": Path(MODEL_NAME).name, "input_file": "input" + suffix}
            JOBS[job_id] = job
            reserved = True
        folder.mkdir(parents=True)
        size = 0
        with (folder / job["input_file"]).open("wb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, f"文件不得超过 {MAX_BYTES // (1024 * 1024)} MB")
                target.write(chunk)
        if not size:
            raise HTTPException(400, "文件为空")
        update(job_id, status="queued", size_bytes=size)
        POOL.submit(process_job, job_id)
        submitted = True
        return get_job(job_id)
    finally:
        await file.close()
        if not submitted:
            if reserved:
                with LOCK:
                    JOBS.pop(job_id, None)
                shutil.rmtree(folder, ignore_errors=True)
            SLOTS.release()


@app.get("/api/jobs/{job_id}/files/{artifact}")
def artifact(job_id: str, artifact: str, download: bool = False):
    job = get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(409, "结果尚未就绪")
    allowed = {"result.jpg": "image/jpeg", "result.mp4": "video/mp4", "detections.json": "application/json"}
    expected = "result.jpg" if job["kind"] == "image" else "result.mp4"
    if artifact not in {expected, "detections.json"}:
        raise HTTPException(404, "文件不存在")
    path = DATA / job_id / artifact
    if not path.is_file():
        raise HTTPException(404, "结果文件已丢失，请重新检测")
    return FileResponse(path, media_type=allowed[artifact],
                        filename=artifact if download else None)


def frame_result(index, fps, items, elapsed):
    return {"frame_index": index, "timestamp_seconds": round(index / fps, 4),
            "num_detections": len(items), "inference_time_ms": elapsed, "detections": items}


def process_job(job_id):
    folder = DATA / job_id
    job = get_job(job_id)
    source = folder / job["input_file"]
    start = time.perf_counter()
    try:
        update(job_id, status="running", phase="加载模型与检测")
        if job["kind"] == "image":
            image = read_image(source)
            annotated, items, elapsed = detector.infer(image, job["confidence"], job["iou"])
            if not cv2.imwrite(str(folder / "result.jpg"), annotated):
                raise ValueError("无法保存标注图片")
            report = {"model": job["model"], "kind": "image", "bbox_format": "xyxy pixels",
                      "width": image.shape[1], "height": image.shape[0],
                      **frame_result(0, 1, items, elapsed)}
            (folder / "detections.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            summary = {"num_detections": len(items), "class_counts": dict(Counter(i["label"] for i in items)),
                       "detections": items, "inference_time_ms": elapsed, "width": image.shape[1], "height": image.shape[0]}
            update(job_id, processed_frames=1, total_frames=1)
        else:
            summary = process_video(job, source, folder)
        update(job_id, status="completed", phase="检测完成", progress=100, summary=summary,
               elapsed_seconds=round(time.perf_counter() - start, 2),
               result_url=f"/api/jobs/{job_id}/files/result.{'jpg' if job['kind'] == 'image' else 'mp4'}",
               json_url=f"/api/jobs/{job_id}/files/detections.json")
    except Exception as exc:
        log.exception("Job %s failed", job_id)
        update(job_id, status="failed", error=f"处理失败：{str(exc)[:400]}")
        for name in ("result.mp4", "result.jpg", "detections.json"):
            (folder / name).unlink(missing_ok=True)
    finally:
        source.unlink(missing_ok=True)
        (folder / "annotated.avi").unlink(missing_ok=True)
        SLOTS.release()


def process_video(job, source, folder):
    cap = cv2.VideoCapture(str(source))
    writer = None
    count, detection_count, inference_ms = 0, 0, 0.0
    classes = Counter()
    try:
        if not cap.isOpened():
            raise ValueError("无法解码视频，请使用有效的 MP4/H.264 文件")
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or fps > 240:
            raise ValueError("视频帧率无效或超过 240 FPS")
        if total > fps * MAX_VIDEO_SECONDS:
            raise ValueError(f"视频最长 {MAX_VIDEO_SECONDS} 秒")
        update(job["id"], total_frames=max(0, total))
        width = height = None
        with (folder / "detections.json").open("w", encoding="utf-8") as report:
            report.write(json.dumps({"model": job["model"], "kind": "video", "fps": fps,
                                     "bbox_format": "xyxy pixels", "frame_index_base": 0})[:-1] + ', "frames": [')
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if count >= math.ceil(fps * MAX_VIDEO_SECONDS):
                    raise ValueError(f"视频最长 {MAX_VIDEO_SECONDS} 秒")
                if writer is None:
                    height, width = frame.shape[:2]
                    if width * height > 3840 * 2160:
                        raise ValueError("视频分辨率不得超过 4K 像素数")
                    writer = cv2.VideoWriter(str(folder / "annotated.avi"), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width + width % 2, height + height % 2))
                    if not writer.isOpened():
                        raise ValueError("视频编码器初始化失败")
                annotated, items, elapsed = detector.infer(frame, job["confidence"], job["iou"])
                if width % 2 or height % 2:
                    annotated = cv2.copyMakeBorder(annotated, 0, height % 2, 0, width % 2, cv2.BORDER_CONSTANT)
                writer.write(annotated)
                if count:
                    report.write(",")
                json.dump(frame_result(count, fps, items, elapsed), report, ensure_ascii=False)
                count += 1
                detection_count += len(items)
                inference_ms += elapsed
                classes.update(item["label"] for item in items)
                if count == 1 or count % 5 == 0:
                    update(job["id"], processed_frames=count, progress=min(95, round(count / total * 95)) if total > 0 else 0)
            report.write('], "processed_frames": ' + str(count) + "}")
        if count == 0:
            raise ValueError("视频中没有可读取的帧")
        if total > 0 and count < total:
            raise ValueError(f"视频提前解码结束（{count}/{total} 帧），请重新编码后上传")
    finally:
        cap.release()
        if writer is not None:
            writer.release()
    update(job["id"], phase="生成浏览器可播放的视频", progress=97, processed_frames=count, total_frames=count)
    # H.264/yuv420p supports browser playback; pad odd dimensions rather than scale.
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(folder / "annotated.avi"),
               "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-vf",
               "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(folder / "result.mp4")]
    result = subprocess.run(command, capture_output=True, timeout=600)
    if result.returncode:
        log.error("ffmpeg: %s", result.stderr.decode(errors="replace")[-2000:])
        raise ValueError("视频转码失败，请检查 FFmpeg 和可用磁盘空间")
    return {"num_detections": detection_count, "class_counts": dict(classes), "fps": fps,
            "duration_seconds": round(count / fps, 3), "width": width, "height": height,
            "inference_time_ms": round(inference_ms / count, 2)}


# Register the SPA last so /api routes always win. Build once to serve both on :8000.
DIST = ROOT / "frontend" / "dist"
if DIST.is_dir():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
