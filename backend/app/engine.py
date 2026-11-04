"""One lazily loaded model; serialized access protects Ultralytics' predictor."""
import os
import threading
import time
from pathlib import Path

import cv2

MODEL_NAME = os.getenv("YOLO_MODEL", "yolov8n.pt")
DEVICE = os.getenv("YOLO_DEVICE", "cpu")


class Detector:
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    def infer(self, image, confidence, iou):
        with self._lock:
            if self._model is None:
                from ultralytics import YOLO
                self._model = YOLO(MODEL_NAME)
                if self._model.task != "detect":
                    raise ValueError("YOLO_MODEL 必须是目标检测模型")
            started = time.perf_counter()
            result = self._model.predict(image, conf=confidence, iou=iou,
                                         device=DEVICE, verbose=False)[0]
            elapsed = (time.perf_counter() - started) * 1000
            items = []
            for coordinates, score, category in zip(result.boxes.xyxy.cpu().tolist(),
                                                    result.boxes.conf.cpu().tolist(),
                                                    result.boxes.cls.cpu().tolist()):
                items.append({"class_id": int(category), "label": result.names[int(category)],
                              "confidence": round(score, 5),
                              "bbox": [round(v, 2) for v in coordinates]})
            return result.plot(), items, round(elapsed, 2)


detector = Detector()


def read_image(path: Path):
    # PIL verifies the actual contents and handles EXIF orientation consistently.
    import numpy as np
    from PIL import Image, ImageOps
    with Image.open(path) as image:
        if image.width * image.height > 25_000_000:
            raise ValueError("图片不得超过 2500 万像素")
        rgb = np.array(ImageOps.exif_transpose(image).convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
