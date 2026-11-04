import { loadModel, infer, draw } from './engine.js'
import { Input, ALL_FORMATS, BlobSource, CanvasSink, Output, BufferTarget, Mp4OutputFormat,
  WebMOutputFormat, CanvasSource, canEncodeVideo } from 'mediabunny'

const jobs = new Map()
let processing = false
const cancelled = new Set()
const limits = { status: 'ok', model: 'YOLOv8n ONNX', device: '浏览器 CPU', max_upload_mb: 50, max_video_seconds: 30 }
const delay = () => new Promise(resolve => setTimeout(resolve, 0))
const blobUrl = value => URL.createObjectURL(value)
const reportUrl = report => blobUrl(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
const check = id => { if (cancelled.has(id)) throw new Error('任务已取消') }
const countClasses = items => items.reduce((counts, item) => { counts[item.label] = (counts[item.label] || 0) + 1; return counts }, {})
function cleanup(job) { for (const key of ['result_url', 'json_url']) if (job[key]) URL.revokeObjectURL(job[key]) }
export function cancel(id) { cancelled.add(id) }

export async function request(url, options = {}) {
  if (url === '/api/health') return limits
  if (url === '/api/jobs') return [...jobs.values()].sort((a, b) => b.created_at - a.created_at).map(j => ({ ...j }))
  const id = url.split('/')[3], job = jobs.get(id)
  if (!job) throw new Error('任务不存在')
  if (options.method === 'DELETE') {
    if (['queued', 'running'].includes(job.status)) throw new Error('任务尚未结束')
    cleanup(job); jobs.delete(id); return null
  }
  return { ...job }
}

export function submit(file, confidence, iou) {
  if (processing) throw new Error('请先等待当前浏览器检测任务结束')
  if (jobs.size >= 10) throw new Error('本次页面最多保存 10 个任务，请删除旧结果后重试')
  const kind = /\.(jpg|jpeg|png|webp|bmp)$/i.test(file.name) ? 'image' : 'video'
  const job = { id: crypto.randomUUID(), filename: file.name, kind, model: limits.model, confidence, iou,
    created_at: Date.now() / 1000, status: 'queued', progress: 0, processed_frames: 0, total_frames: 0 }
  jobs.set(job.id, job); processing = true
  setTimeout(async () => {
    try { await process(job, file) }
    catch (error) { cleanup(job); job.status = 'failed'; job.error = error.message || '浏览器处理失败' }
    finally { processing = false; cancelled.delete(job.id) }
  }, 0)
  return { ...job }
}

async function process(job, file) {
  const started = performance.now()
  job.status = 'running'
  await loadModel(message => { job.phase = message })
  check(job.id)
  job.phase = '浏览器本地检测中，请保持页面打开'
  if (job.kind === 'image') {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    try {
      const width = bitmap.width, height = bitmap.height
      if (width * height > 12_000_000) throw new Error('在线版图片不得超过 1200 万像素')
      const { items, elapsed } = await infer(bitmap, width, height, job.confidence, job.iou)
      check(job.id)
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height
      draw(canvas, bitmap, items, width, height)
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .93))
      if (!blob) throw new Error('图片导出失败')
      job.result_url = blobUrl(blob)
      job.json_url = reportUrl({ model: job.model, kind: 'image', bbox_format: 'xyxy pixels', width, height,
        num_detections: items.length, inference_time_ms: elapsed, detections: items })
      job.summary = { width, height, num_detections: items.length, class_counts: countClasses(items), detections: items, inference_time_ms: elapsed }
      job.processed_frames = job.total_frames = 1
      job.result_filename = 'result.jpg'
    } finally { bitmap.close() }
  } else await processVideo(job, file)
  job.elapsed_seconds = Number(((performance.now() - started) / 1000).toFixed(2))
  job.status = 'completed'; job.progress = 100; job.phase = '检测完成'
}

async function processVideo(job, file) {
  if (!globalThis.VideoDecoder || !globalThis.VideoEncoder) throw new Error('此浏览器不支持视频编解码，请使用最新版桌面 Chrome 或 Edge；图片检测仍可使用')
  const input = new Input({ source: new BlobSource(file), formats: ALL_FORMATS })
  let output
  try {
    const track = await input.getPrimaryVideoTrack()
    if (!track || !await track.canDecode()) throw new Error('无法解码视频，建议使用 MP4/H.264 格式')
    const duration = await track.computeDuration()
    const width = track.displayWidth, height = track.displayHeight
    if (!Number.isFinite(duration) || duration <= 0 || duration > 30.05) throw new Error('在线版视频限 30 秒以内')
    if (width * height > 1920 * 1080) throw new Error('在线版视频最高支持 1080p 像素数')
    const stats = await track.computePacketStats()
    if (stats.packetCount > 1800) throw new Error('在线版最多处理 1800 帧，请裁剪短片后重试')
    job.total_frames = stats.packetCount
    const canvas = document.createElement('canvas')
    canvas.width = width + width % 2; canvas.height = height + height % 2
    const encodeOptions = { width: canvas.width, height: canvas.height, bitrate: 2_500_000 }
    const codec = await canEncodeVideo('avc', encodeOptions) ? 'avc' : await canEncodeVideo('vp9', encodeOptions) ? 'vp9' : null
    if (!codec) throw new Error('浏览器没有可用的视频编码器，建议使用最新版桌面 Chrome/Edge')
    const mp4 = codec === 'avc'
    const target = new BufferTarget()
    output = new Output({ target, format: mp4 ? new Mp4OutputFormat({ fastStart: 'in-memory' }) : new WebMOutputFormat() })
    const source = new CanvasSource(canvas, { codec, bitrate: 2_500_000 })
    output.addVideoTrack(source)
    await output.start()
    const sink = new CanvasSink(track, { poolSize: 2 })
    const frames = [], classes = {}; let totalDetections = 0, totalMs = 0, firstTime = null
    for await (const frame of sink.canvases()) {
      check(job.id)
      if (frames.length >= 1800) throw new Error('视频超过 1800 帧限制')
      if (firstTime === null) firstTime = frame.timestamp
      const { items, elapsed } = await infer(frame.canvas, width, height, job.confidence, job.iou)
      draw(canvas, frame.canvas, items, width, height)
      await source.add(frame.timestamp - firstTime, frame.duration)
      frames.push({ frame_index: frames.length, timestamp_seconds: Number((frame.timestamp - firstTime).toFixed(6)),
        num_detections: items.length, inference_time_ms: elapsed, detections: items })
      for (const item of items) classes[item.label] = (classes[item.label] || 0) + 1
      totalDetections += items.length; totalMs += elapsed
      job.processed_frames = frames.length
      job.progress = Math.min(97, Math.round(frames.length / Math.max(1, job.total_frames) * 97))
      await delay()
    }
    if (!frames.length) throw new Error('未读到有效视频帧')
    check(job.id)
    job.phase = '正在完成视频编码'
    source.close(); await output.finalize()
    job.result_url = blobUrl(new Blob([target.buffer], { type: mp4 ? 'video/mp4' : 'video/webm' }))
    job.result_filename = mp4 ? 'result.mp4' : 'result.webm'
    job.json_url = reportUrl({ model: job.model, kind: 'video', bbox_format: 'xyxy pixels', width, height,
      processed_frames: frames.length, source_duration_seconds: duration, frames })
    job.summary = { num_detections: totalDetections, class_counts: classes, inference_time_ms: Number((totalMs / frames.length).toFixed(2)), width, height }
    job.total_frames = frames.length
  } catch (error) {
    if (output && output.state !== 'finalized' && output.state !== 'canceled') await output.cancel().catch(() => {})
    throw error
  } finally { input.dispose() }
}

// History and object URLs belong only to this page session, never to a shared server.
addEventListener('pagehide', () => { jobs.forEach(cleanup) })
