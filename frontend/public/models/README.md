# Browser model

`yolov8n.onnx` is exported from the official Ultralytics YOLOv8n weights included at the repository root.

Input: float32 RGB, CHW, 1 x 3 x 416 x 416, letterbox padding 114, normalized to 0–1.
Output: 1 x 84 x 3549, with class-aware NMS implemented in `src/browser/postprocess.js`.

Export: Ultralytics 8.4.202, ONNX opset 17, `imgsz=416`, `dynamic=False`, `simplify=False`.

The model retains its upstream licensing obligations. See https://www.ultralytics.com/license and the root LICENSE.
