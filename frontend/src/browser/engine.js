import * as ort from 'onnxruntime-web/wasm'
import { decode } from './postprocess.js'

const SIZE = 416
let session, loading
ort.env.wasm.numThreads = 1
ort.env.wasm.wasmPaths = new URL(`${import.meta.env.BASE_URL}ort/`, location.origin).href
export async function loadModel(progress = () => {}) {
  if (session) return session
  if (!loading) loading = (async () => {
    progress('首次加载模型，约 13 MB，请稍候')
    const response = await fetch(`${import.meta.env.BASE_URL}models/yolov8n.onnx`)
    if (!response.ok) throw new Error('模型下载失败，请检查网络后重试')
    const bytes = await response.arrayBuffer()
    progress('正在初始化浏览器推理引擎')
    session = await ort.InferenceSession.create(bytes, { executionProviders: ['wasm'], graphOptimizationLevel: 'all' })
    return session
  })().catch(e => { loading = null; throw e })
  return loading
}

export async function infer(source, width, height, confidence, iou) {
  const model = await loadModel()
  const start = performance.now()
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = SIZE
  const context = canvas.getContext('2d', { willReadFrequently: true })
  const scale = Math.min(SIZE / width, SIZE / height)
  const resizedWidth = Math.round(width * scale), resizedHeight = Math.round(height * scale)
  const left = Math.round((SIZE - resizedWidth) / 2 - .1), top = Math.round((SIZE - resizedHeight) / 2 - .1)
  context.fillStyle = 'rgb(114,114,114)'; context.fillRect(0, 0, SIZE, SIZE)
  context.drawImage(source, left, top, resizedWidth, resizedHeight)
  const rgba = context.getImageData(0, 0, SIZE, SIZE).data
  const pixels = SIZE * SIZE, values = new Float32Array(pixels * 3)
  for (let i = 0; i < pixels; i++) {
    values[i] = rgba[i * 4] / 255
    values[pixels + i] = rgba[i * 4 + 1] / 255
    values[2 * pixels + i] = rgba[i * 4 + 2] / 255
  }
  const tensor = new ort.Tensor('float32', values, [1, 3, SIZE, SIZE])
  let outputs
  try {
    outputs = await model.run({ [model.inputNames[0]]: tensor })
    const output = outputs[model.outputNames[0]]
    const items = decode(output.data, output.dims[2], { scale, left, top, width, height }, confidence, iou)
    return { items, elapsed: Number((performance.now() - start).toFixed(2)) }
  } finally {
    tensor.dispose()
    if (outputs) Object.values(outputs).forEach(value => value.dispose())
  }
}

export function draw(canvas, source, items, width, height) {
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(source, 0, 0, width, height)
  const font = Math.max(14, Math.round(Math.min(width, height) / 35))
  ctx.font = `600 ${font}px system-ui, sans-serif`; ctx.textBaseline = 'top'
  ctx.lineWidth = Math.max(2, Math.round(Math.min(width, height) / 200))
  for (const item of items) {
    const [x1, y1, x2, y2] = item.bbox, color = `hsl(${(item.class_id * 47 + 225) % 360} 80% 53%)`
    const text = `${item.label} ${(item.confidence * 100).toFixed(0)}%`
    const textWidth = ctx.measureText(text).width + 10
    const labelX = Math.max(0, Math.min(x1, width - textWidth))
    const labelY = Math.max(0, y1 - font - 7)
    ctx.strokeStyle = color; ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
    ctx.fillStyle = color; ctx.fillRect(labelX, labelY, textWidth, font + 7)
    ctx.fillStyle = '#fff'; ctx.fillText(text, labelX + 5, labelY + 2)
  }
}
