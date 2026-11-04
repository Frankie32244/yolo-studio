# YOLO Studio · 视觉检测工作台

一个可本地运行的中文目标检测网站：**Vue 3 + Vite 前端，FastAPI 后端，Ultralytics YOLOv8n 推理**。

参考 [Live YOLO Webcam Demo](https://huggingface.co/spaces/indersingh17188/live-yolo-webcam-demo) 的使用思路后独立实现。已先检查其代码和许可；原仓库没有声明复用许可，所以未复制其源码。详细证据、提交和依赖许可见 [原项目检查](UPSTREAM_REVIEW.md)。本交付原创代码采用 AGPL-3.0-or-later，见 [LICENSE](../LICENSE)。

## 功能

- 图片：JPG / JPEG / PNG / WEBP / BMP，自动处理 EXIF 旋转，显示检测框、类别、置信度、坐标和推理耗时。
- 视频：MP4 / MOV / AVI / MKV / WEBM，OpenCV 逐帧解码，每帧均进行 YOLO 检测，不抽帧；后台排队，前端轮询进度。
- 下载：带框 JPEG、H.264 MP4、结构化 JSON；视频 JSON 含每帧检测结果与时间戳。
- 支持置信度、IoU 调节，原图/结果切换，历史任务、删除任务、异常提示。
- 上传分块落盘、文件和时长限制、模型惰性加载、单 worker 串行推理、任务状态持久化、重启中断标记。
- Vite 开发代理；构建后 FastAPI 同端口提供前端，无需配置 CORS。无 CDN 或外部字体依赖。

## 环境

- 推荐 Python 3.11 或 3.12，Node.js 22.12+，npm 或 pnpm 11。
- CPU 可以运行；推荐至少 8 GB 内存、数 GB 空闲磁盘。CPU 视频检测可能明显慢于实时。
- 首次安装依赖、首次下载 `yolov8n.pt` 需要联网。模型约 6 MB，PyTorch 依赖较大。

## 快速启动（Windows PowerShell）

**Windows 双击启动：直接运行根目录 `start.cmd`。** 自动建立 `.venv`、安装后端依赖，并在服务就绪后打开浏览器。首次安装需要联网；已包含构建后的前端，不需要安装 Node。若 8000 端口被占用，会自动选择 8001–8020。保持启动窗口打开，按 Ctrl+C 停止。项目可整体移动，启动脚本自动使用所在文件夹。

在解压后的 `yolo-web` 目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm install
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

打开 **http://127.0.0.1:8000**。保持该终端运行；按 Ctrl+C 关闭。第一次点“开始检测”会下载并加载模型，耗时较长属于正常现象。页面“服务已连接”只代表 API 在线，不代表权重已加载。

也可以使用 pnpm：在 frontend 目录运行 `pnpm install --frozen-lockfile`、`pnpm build`，仓库已提供 pnpm 锁文件和 esbuild 安装许可配置。npm 路径首次安装会生成自己的 package-lock.json。

## Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cd frontend
npm install
npm run build
cd ..
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

无桌面 Linux 如出现 `libGL.so.1` 缺失，Debian/Ubuntu 可安装 `libgl1 libglib2.0-0`。Dockerfile 已安装。

## 前后端分别开发

终端 A（项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

终端 B：

```powershell
cd frontend
npm run dev
```

访问 http://127.0.0.1:5173 。Vite 将 `/api` 转发至后端 8000。生产构建后必须重启后端，才能挂载新生成的 `frontend/dist`。

## Docker

```bash
docker compose up --build
```

访问 http://127.0.0.1:8000 。Docker 构建会安装前后端依赖并预下载默认模型；运行期间使用命名卷保存任务。关闭：`docker compose down`（保留卷）。本次交付未在 Docker 引擎内实测，已提供配置供具备 Docker 的环境使用。

## 自定义配置

启动后端前设置环境变量，不读取 `.env` 文件；也可自行使用 uvicorn 的 `--env-file` 参数。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `YOLO_MODEL` | `yolov8n.pt` | 受信任的 Ultralytics 目标检测权重文件或名称，由管理员指定 |
| `YOLO_DEVICE` | `cpu` | CPU 用 `cpu`；正确安装 CUDA PyTorch 后可用 `0` |
| `YOLO_DATA_DIR` | 项目下 `data/` | 上传暂存、结果和任务状态目录 |
| `MAX_UPLOAD_MB` | `200` | 单文件最大 MiB |
| `MAX_VIDEO_SECONDS` | `300` | 最长视频时长 |
| `MAX_JOBS` | `100` | 最大保存任务数；达到上限后先删除旧任务 |

Windows 示例：

```powershell
$env:YOLO_MODEL='D:\models\yolov8n.pt'
$env:YOLO_DEVICE='cpu'
$env:MAX_UPLOAD_MB='100'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

离线使用：先联网完成依赖安装和模型下载，或从可信官方来源取得 `.pt` 权重后指定绝对路径。自定义模型必须是 `detect` 任务，标签由权重的 `names` 提供。默认 COCO 模型识别 80 类，不能直接识别任意自定义类别。

## API

交互式接口文档：http://127.0.0.1:8000/docs

| 方法 | 地址 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | API、模型和限制状态 |
| POST | `/api/jobs` | multipart 上传：`file`、`confidence`、`iou`；返回 202 和任务 ID |
| GET | `/api/jobs` | 当前服务的共享任务列表，最新在前 |
| GET | `/api/jobs/{id}` | 任务状态、进度、统计和结果链接 |
| GET | `/api/jobs/{id}/files/result.jpg` | 图片结果 |
| GET | `/api/jobs/{id}/files/result.mp4` | 视频结果（支持 Range） |
| GET | `/api/jobs/{id}/files/detections.json` | 完整检测结果 |
| DELETE | `/api/jobs/{id}` | 删除已完成或失败任务及所有文件 |

下载时在文件链接后附加 `?download=true`。任务状态依次为 `queued → running → completed/failed`。队列满返回 429，存储任务达到上限返回 507，过大文件返回 413。上传阶段属于请求过程，列表中可能短暂出现 `uploading`。

```bash
curl -F "file=@example.jpg" -F "confidence=0.25" -F "iou=0.45" http://127.0.0.1:8000/api/jobs
```

Windows PowerShell 请用 `curl.exe`。再用返回的 ID 查询任务即可。图片结果示例：

```json
{
  "model": "yolov8n.pt",
  "kind": "image",
  "bbox_format": "xyxy pixels",
  "width": 810,
  "height": 1080,
  "frame_index": 0,
  "timestamp_seconds": 0.0,
  "num_detections": 1,
  "inference_time_ms": 120.5,
  "detections": [
    {"class_id": 0, "label": "person", "confidence": 0.91, "bbox": [10.2, 20.4, 300.5, 700.6]}
  ]
}
```

这是字段格式示例，不是固定模型输出。`bbox` 为方向校正后的原图像素坐标 `[左, 上, 右, 下]`，不是归一化坐标。视频 JSON 的 `frames` 是逐帧数组，`frame_index` 从 0 开始，`timestamp_seconds = frame_index / fps`。`inference_time_ms` 包含模型预处理、推理、后处理，不含首次加载和下载，不含画框、转码及上传耗时。任务的 `elapsed_seconds` 是后台处理总耗时。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
cd backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

自动测试用确定性检测器隔离接口行为，视频测试仍使用真实 OpenCV 和 FFmpeg。真实模型测试见 [验证记录](VALIDATION.md)。前端验证：`cd frontend` 后执行 `npm run build`。

## 边界与部署说明

- 这是可运行的单机工作台。仅启动 **1 个 uvicorn worker**：内存任务索引、线程锁、队列不跨进程共享。多实例部署需替换为 Redis/Celery 等共享队列。
- 同时最多 4 个上传/排队/执行任务，单个检测 worker 串行运行。任务状态在本地持久化，重启会将中断任务标为失败，不自动续传或续算。
- 原始文件处理完成后删除，结果保留到手动删除任务。中间 MJPEG 视频体积可能较大；部署前预留磁盘。上传文件限制是在应用收到 multipart 并解析之后检查；互联网部署需反向代理额外限制请求体大小、超时和速率。
- 默认监听本机，没有登录、用户隔离、自动过期、审计或公网限流。该服务所有访问者共享任务列表。对外开放前需增加身份验证、用户级存储、HTTPS、访问控制和资源配额。
- 不含目标追踪或去重，视频“检测目标”为所有帧检测框总数。导出视频不含原音轨；使用源平均 FPS 输出恒定帧率，变帧率视频不保留原始逐帧时间戳。
- 图片限制 2500 万像素；视频限制 4K 像素数和 240 FPS，默认最长 300 秒。损坏或不支持的编码会显示失败；建议重编码为 MP4/H.264 后重试。
- CPU/GPU 的结果与速度会有差异，不能承诺固定耗时或识别准确率。需要业务特定类别时，应自行训练适用权重。

## 文件结构

```text
yolo-web/
├── backend/
│   ├── app/{main.py,engine.py}    # API、队列、视频处理、模型封装
│   ├── tests/test_api.py         # 接口与视频链路测试
│   └── requirements*.txt
├── frontend/
│   ├── src/{App.vue,style.css,main.js}
│   ├── dist/                    # 已构建前端，可直接由 FastAPI 提供
│   ├── package.json
│   └── pnpm-lock.yaml
├── docs/                        # 原项目检查和验证记录
├── Dockerfile
├── compose.yaml
└── LICENSE
```

UI 已构建，因此只安装后端依赖即可使用现成的 `frontend/dist`。修改前端后请重新构建。
