"""Contract tests use a deterministic detector. Real YOLO smoke test is separate."""
import importlib
import io
import json
import sys
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("YOLO_DATA_DIR", str(tmp_path / "jobs"))
    sys.modules.pop("app.main", None)
    main = importlib.import_module("app.main")
    def infer(image, confidence, iou):
        return image, [{"label": "person", "class_id": 0, "confidence": 0.9, "bbox": [1, 1, 12, 12]}], 1.2
    monkeypatch.setattr(main.detector, "infer", infer)
    with TestClient(main.app) as value:
        yield value, main


def wait(client, job_id):
    for _ in range(300):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(.03)
    raise AssertionError("Job did not finish")


def image_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "red").save(buf, "PNG")
    return buf.getvalue()


def test_image_contract_download_delete(client):
    api, main = client
    response = api.post("/api/jobs", files={"file": ("test.png", image_bytes(), "image/png")})
    assert response.status_code == 202
    job = wait(api, response.json()["id"])
    assert job["status"] == "completed", job
    assert job["summary"]["num_detections"] == 1
    report = api.get(job["json_url"]).json()
    assert report["detections"][0]["bbox"] == [1, 1, 12, 12]
    assert api.get(job["result_url"]).headers["content-type"] == "image/jpeg"
    download = api.get(job["result_url"] + "?download=true")
    assert "attachment" in download.headers["content-disposition"]
    assert not (main.DATA / job["id"] / "input.png").exists()
    assert api.get(f"/api/jobs/{job['id']}/files/job.json").status_code == 404
    assert api.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert api.get(f"/api/jobs/{job['id']}").status_code == 404


def test_invalid_inputs(client):
    api, main = client
    assert api.post("/api/jobs", files={"file": ("a.exe", b"123")}).status_code == 415
    assert api.post("/api/jobs", files={"file": ("a.png", b"")}).status_code == 400
    assert api.post("/api/jobs", files={"file": ("a.png", image_bytes())}, data={"confidence": 2}).status_code == 422
    main.MAX_BYTES = 5
    assert api.post("/api/jobs", files={"file": ("a.png", image_bytes())}).status_code == 413
    assert not api.get("/api/jobs").json()


def test_corrupt_image(client):
    api, _ = client
    response = api.post("/api/jobs", files={"file": ("bad.png", b"invalid")})
    job = wait(api, response.json()["id"])
    assert job["status"] == "failed"
    assert api.get(f"/api/jobs/{job['id']}/files/result.jpg").status_code == 409


def test_video_all_frames_and_h264(client, tmp_path):
    api, main = client
    source = tmp_path / "source.avi"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"MJPG"), 6, (64, 48))
    for i in range(6):
        writer.write(np.full((48, 64, 3), i * 30, dtype=np.uint8))
    writer.release()
    response = api.post("/api/jobs", files={"file": ("clip.avi", source.read_bytes(), "video/x-msvideo")})
    job = wait(api, response.json()["id"])
    assert job["status"] == "completed", job
    assert job["processed_frames"] == 6
    assert job["summary"]["num_detections"] == 6
    report = api.get(job["json_url"]).json()
    assert [f["frame_index"] for f in report["frames"]] == list(range(6))
    assert report["frames"][5]["timestamp_seconds"] == round(5 / 6, 4)
    output = main.DATA / job["id"] / "result.mp4"
    assert b"avc1" in output.read_bytes()
    capture = cv2.VideoCapture(str(output))
    assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == 6
    capture.release()
    assert api.get(job["result_url"], headers={"Range": "bytes=0-31"}).status_code == 206


def test_storage_capacity_and_running_delete(client):
    api, main = client
    main.MAX_JOBS = 0
    assert api.post("/api/jobs", files={"file": ("a.png", image_bytes())}).status_code == 507
    main.JOBS["known"] = {"id": "known", "status": "running"}
    assert api.delete("/api/jobs/known").status_code == 409
