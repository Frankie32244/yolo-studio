# 原项目代码与许可检查

检查日期：2026-11-04。公开 API 所示当前提交：`d945c71ff1a5a8f26b03d83e6912cd6078c72d92`。

- 项目：https://huggingface.co/spaces/indersingh17188/live-yolo-webcam-demo
- 文件列表：https://huggingface.co/api/spaces/indersingh17188/live-yolo-webcam-demo/tree/main
- 元数据：https://huggingface.co/api/spaces/indersingh17188/live-yolo-webcam-demo
- 源码：https://huggingface.co/spaces/indersingh17188/live-yolo-webcam-demo/blob/main/app.py
- 说明：https://huggingface.co/spaces/indersingh17188/live-yolo-webcam-demo/blob/main/README.md

## 核查结果

仓库只有 `.gitattributes`、`README.md`、`app.py`、`requirements.txt` 四个文件。`app.py` 使用 Gradio、Ultralytics YOLO、Pillow，启动时加载 `yolov8n.pt`，对上传或摄像头拍摄的静态图片推理，用 Pillow 绘制矩形和文字，返回图片与 JSON 字符串。不是连续摄像头流检测；没有上传视频逐帧处理，也没有结果下载接口。依赖中很多组件未锁定版本。

未发现 LICENSE 文件；README front matter 和 Space cardData 均没有 `license` 字段，README 正文也未授予复用许可。**公开可读不意味着允许复制和再分发。** 本交付只参考功能思路，Vue、FastAPI、队列、视频处理和 UI 均独立编写，没有复制原项目源码或把原项目当作已获许可的依赖。若以后直接合并其代码，应先向作者获取适用许可。

## 本实现及依赖

本交付原创源码采用 GNU AGPL-3.0-or-later，全文见根目录 LICENSE。上游项目许可不明的情况不因本交付的许可而改变。

Ultralytics 提供 AGPL-3.0 和 Enterprise 许可路径。使用、修改、网络提供服务和再分发时，应遵守相应许可义务；闭源用途请按供应商条款确认 Enterprise 方案。本交付不替你购买企业许可，也不宣称上游权重可按 MIT 使用。

- Ultralytics 许可说明：https://www.ultralytics.com/license
- Ultralytics 源码许可：https://github.com/ultralytics/ultralytics/blob/main/LICENSE
- YOLOv8 说明：https://docs.ultralytics.com/models/yolov8/
- Vue（MIT）：https://github.com/vuejs/core/blob/main/LICENSE
- FastAPI（MIT）：https://github.com/fastapi/fastapi/blob/master/LICENSE
- OpenCV：https://github.com/opencv/opencv/blob/4.x/LICENSE
- imageio-ffmpeg：https://github.com/imageio/imageio-ffmpeg

FFmpeg 二进制与 libx264 具有各自的许可要求，重新分发 Docker 镜像时也需保留适用声明并履行相关义务。GitHub 仓库包含来自 Ultralytics 官方发布的默认 yolov8n.pt 权重，保留适用许可要求。test-pics 中是用户提供的功能截图；不包含完整第三方数据集或本地检测任务文件。
