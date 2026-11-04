# 免费浏览器在线版

地址：https://Frankie32244.github.io/yolo-studio/

GitHub Pages 托管页面、公开模型与浏览器推理引擎，检测在访客设备运行。无需安装 Python、不需要付费服务器；用户素材不上传到后端。原 FastAPI 本地版继续保留。

## 两种运行方式

| 项目 | 在线版 | 本地版 |
| --- | --- | --- |
| 启动 | 打开网页 | 下载后双击 start.cmd |
| 模型 | YOLOv8n ONNX，416 输入 | Ultralytics YOLOv8n，默认 640 输入 |
| 首次使用 | 下载约 13 MB 模型和约 11 MB WASM 引擎 | 安装 Python 依赖 |
| 文件大小 | 最大 50 MiB | 最大 200 MiB |
| 图片 | 最大 1200 万像素 | 最大 2500 万像素 |
| 视频 | 最长 30 秒，最高 1080p 像素数，最多 1800 帧 | 最长 300 秒，最高 4K 像素数 |
| 导出 | JPEG、JSON、优先 MP4，不支持时回退 WebM | JPEG、JSON、H.264 MP4 |
| 音轨 | 不保留 | 不保留 |
| 记录 | 当前页面会话内，最多 10 项；刷新后清空 | 本地磁盘持久化 |

视频使用 Mediabunny + WebCodecs 按源时间戳逐帧解码、检测和重新编码，不通过定时截屏或抽帧冒充逐帧处理。目标数仍是检测框累计数，不是独立目标数。奇数宽高会在右侧或底部补一像素以兼容编码器。

推荐最新版桌面 Chrome / Edge，视频输入推荐 MP4/H.264。浏览器不支持源编码或 WebCodecs 时会提示错误；图片功能可单独使用。不同设备的速度会有差异；检测时保持页面打开，可点击“取消当前检测”。小输入在线模型的结果可能与本地模型不同。

浏览器普通缓存可能缓存下载的公开模型；没有 Service Worker 离线安装，不保证首次离线打开可用。不要直接用 file:// 打开构建目录，需使用 HTTP(S) 服务器。

## 构建与发布

`.github/workflows/pages.yml` 在 main 更新时自动运行测试、构建并部署。仓库 Settings → Pages 使用 **GitHub Actions** 作为构建来源。

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm build:pages
```

在线产物为 `frontend/dist-pages`，基础路径 `/yolo-studio/`。普通 `pnpm build` 仍生成本地 FastAPI 版 `frontend/dist`。部署到不同仓库名时修改 `vite.config.js` 的 pages base。

模型位于 `frontend/public/models/yolov8n.onnx`，推理引擎位于 `frontend/public/ort`，都随站点托管，不调用第三方推理服务。

## 许可

ONNX 模型由本仓库官方 Ultralytics 权重转换，保留适用的 AGPL/Enterprise 许可要求；见 [模型说明](../frontend/public/models/README.md)。ONNX Runtime Web 为 MIT，Mediabunny 为 MPL-2.0。第三方许可全文见 [licenses](licenses/)。
