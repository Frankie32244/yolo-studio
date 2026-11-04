<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import VisionMark from './VisionMark.vue'
import { ScanLine, Image, Film, UploadCloud, ArrowUpRight, Download, Check, LoaderCircle, SlidersHorizontal, ChevronRight, Clock3, Trash2, AlertCircle, Layers, Box, RefreshCw } from 'lucide-vue-next'

const mode = ref('image'), file = ref(null), preview = ref(''), drag = ref(false)
const confidence = ref(0.25), iou = ref(0.45), jobs = ref([]), selected = ref(null)
const health = ref(null), error = ref(''), sending = ref(false), uploadProgress = ref(0)
const showOriginal = ref(false), input = ref(null), loading = ref(false)
let timer, xhr, destroyed = false
const active = computed(() => jobs.value.find(j => j.id === selected.value))
const busy = computed(() => sending.value || ['queued', 'running', 'uploading'].includes(active.value?.status))
const summary = computed(() => active.value?.summary)
const currentPreview = computed(() => active.value?.status === 'completed' && !showOriginal.value ? active.value.result_url : preview.value)
const currentKind = computed(() => active.value?.kind || mode.value)
const labels = { queued: '排队中', running: '检测中', completed: '已完成', failed: '检测失败', uploading: '上传中' }
const formats = computed(() => mode.value === 'image' ? '.jpg,.jpeg,.png,.webp,.bmp' : '.mp4,.mov,.avi,.mkv,.webm')
const sizeText = n => n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : (n / 1024).toFixed(0) + ' KB'
async function api(url, options) {
  const response = await fetch(url, options)
  if (!response.ok) {
    let data
    try { data = await response.json() } catch { /* generic HTTP message */ }
    throw new Error(typeof data?.detail === 'string' ? data.detail : `请求失败 (${response.status})`)
  }
  return response.status === 204 ? null : response.json()
}
async function refresh() {
  try {
    const [h, list] = await Promise.all([api('/api/health'), api('/api/jobs')])
    if (destroyed) return
    health.value = h; jobs.value = list
  } catch { if (!destroyed) health.value = null }
}
function clearPreview() {
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = ''
}
function changeMode(value) {
  if (sending.value) return
  mode.value = value; file.value = null; selected.value = null; error.value = ''; showOriginal.value = false
  clearPreview()
  if (input.value) input.value.value = ''
}
function choose(value) {
  drag.value = false; error.value = ''
  if (!value || sending.value) return
  const extension = '.' + value.name.split('.').pop().toLowerCase()
  if (!formats.value.split(',').includes(extension)) { error.value = '请选择当前检测类型支持的文件格式'; return }
  if (value.size > (health.value?.max_upload_mb || 200) * 1048576) { error.value = '文件超出上传大小限制'; return }
  if (!value.size) { error.value = '不能上传空文件'; return }
  clearPreview(); preview.value = URL.createObjectURL(value)
  file.value = value; selected.value = null; showOriginal.value = false
}
function selectJob(job) {
  if (sending.value) return
  selected.value = job.id; file.value = null; error.value = ''; showOriginal.value = false
  clearPreview(); mode.value = job.kind
}
async function submit() {
  if (!file.value || sending.value) return
  sending.value = true; error.value = ''; uploadProgress.value = 0
  const data = new FormData()
  data.append('file', file.value); data.append('confidence', confidence.value); data.append('iou', iou.value)
  try {
    const job = await new Promise((resolve, reject) => {
      xhr = new XMLHttpRequest(); xhr.open('POST', '/api/jobs'); xhr.timeout = 300000
      xhr.upload.onprogress = e => { if (e.lengthComputable) uploadProgress.value = Math.round(e.loaded / e.total * 100) }
      xhr.onload = () => {
        let body
        try { body = JSON.parse(xhr.responseText) } catch { reject(new Error('服务器返回了无效响应')); return }
        xhr.status === 202 ? resolve(body) : reject(new Error(typeof body.detail === 'string' ? body.detail : '上传失败，请检查参数'))
      }
      xhr.onerror = () => reject(new Error('连接失败，请检查后端服务'))
      xhr.ontimeout = () => reject(new Error('上传超时，请重试'))
      xhr.onabort = () => reject(new Error('上传已取消'))
      xhr.send(data)
    })
    jobs.value = [job, ...jobs.value.filter(j => j.id !== job.id)]; selected.value = job.id
    await refresh()
  } catch (e) { error.value = e.message }
  finally { sending.value = false; xhr = null }
}
async function removeJob(job) {
  try {
    await api(`/api/jobs/${job.id}`, { method: 'DELETE' })
    jobs.value = jobs.value.filter(j => j.id !== job.id)
    if (selected.value === job.id) { selected.value = null; clearPreview(); file.value = null }
  } catch (e) { error.value = e.message }
}
onMounted(async () => { await refresh(); timer = setInterval(refresh, 1800) })
onUnmounted(() => { destroyed = true; clearInterval(timer); xhr?.abort(); clearPreview() })
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <a class="brand" href="/" aria-label="YOLO Studio 首页"><span class="brand-icon"><VisionMark /></span><span>YOLO<span class="brand-light"> Studio</span></span></a>
      <button class="nav-item active" @click="changeMode('image')"><VisionMark class="nav-vision-mark" />视觉检测<span class="nav-count">01</span></button>
      <div class="history-head"><span>最近任务</span><button class="icon-button" @click="refresh" aria-label="刷新任务"><RefreshCw :size="14" /></button></div>
      <div class="history">
        <div v-if="!jobs.length" class="history-empty"><Clock3 :size="21" /><span>检测记录将在这里显示</span></div>
        <div v-for="job in jobs" :key="job.id" class="history-row" :class="{ selected: selected === job.id }">
          <button class="history-select" @click="selectJob(job)"><component :is="job.kind === 'image' ? Image : Film" :size="16" /><span><b>{{ job.filename }}</b><small :class="job.status">{{ labels[job.status] }}</small></span></button>
          <button v-if="['completed','failed'].includes(job.status)" class="icon-button" @click="removeJob(job)" :aria-label="`删除 ${job.filename}`"><Trash2 :size="13" /></button>
        </div>
      </div>
      <div class="sidebar-bottom"><div class="model-mark">Y8</div><span>Ultralytics YOLO<small>{{ health?.model || 'yolov8n.pt' }} · {{ health?.device || 'CPU' }}</small></span><span class="tiny-dot" :class="{ offline: !health }"></span></div>
    </aside>

    <div class="workspace">
      <header class="topbar"><div>工作空间 <ChevronRight :size="14" /><strong>视觉检测</strong></div><span class="connection"><span class="tiny-dot" :class="{ offline: !health }"></span>{{ health ? '服务已连接' : '正在连接服务' }}</span></header>
      <main>
        <div class="page-title"><div><div class="eyebrow">SEE MORE. UNDERSTAND MORE.</div><h1>每一帧，都有发现<span>。</span></h1><p>上传图片或视频，让 YOLO 为你识别画面中的目标。</p></div><span class="version"><Layers :size="14" /> YOLO WORKSPACE / 1.0</span></div>

        <div class="work-grid">
          <section class="input-panel panel">
            <div class="panel-heading"><span class="step">01</span><h2>上传素材</h2><span class="panel-subtitle">INPUT</span></div>
            <div class="tabs" role="tablist" aria-label="检测类型"><button role="tab" :aria-selected="mode === 'image'" :class="{chosen: mode === 'image'}" @click="changeMode('image')"><Image :size="16" />图片检测</button><button role="tab" :aria-selected="mode === 'video'" :class="{chosen: mode === 'video'}" @click="changeMode('video')"><Film :size="16" />视频检测</button></div>
            <input ref="input" type="file" class="sr-only" :accept="formats" @change="choose($event.target.files[0])" />
            <button class="dropzone" :class="{ dragging: drag, 'has-file': file }" :disabled="sending" @click="input.click()" @dragover.prevent="drag = true" @dragleave.prevent="drag = false" @drop.prevent="choose($event.dataTransfer.files[0])">
              <span class="upload-icon"><component :is="file ? Check : UploadCloud" :size="27" :stroke-width="1.5" /></span><strong>{{ file ? file.name : '将文件拖到这里' }}</strong><span>{{ file ? sizeText(file.size) + ' · 点击重新选择' : '或点击选择本地文件' }}</span><small>{{ mode === 'image' ? 'JPG / PNG / WEBP / BMP' : 'MP4 / MOV / AVI / MKV / WEBM' }}<br>最大 {{ health?.max_upload_mb || 200 }} MB{{ mode === 'video' ? ' · 最长 ' + (health?.max_video_seconds || 300) + ' 秒' : '' }}</small>
            </button>
            <div class="parameter-heading"><SlidersHorizontal :size="16" /><h3>检测参数</h3><span>自定义</span></div>
            <div class="parameter"><label for="confidence">置信度阈值 <span>{{ Number(confidence).toFixed(2) }}</span></label><input id="confidence" v-model.number="confidence" type="range" min="0.01" max="1" step="0.01" :disabled="sending" /><p>数值越高，保留的检测结果越可信。</p></div>
            <div class="parameter"><label for="iou">IoU 阈值 <span>{{ Number(iou).toFixed(2) }}</span></label><input id="iou" v-model.number="iou" type="range" min="0.01" max="1" step="0.01" :disabled="sending" /><p>控制重叠检测框的过滤程度。</p></div>
            <button class="start-button" :disabled="!file || sending || !health" @click="submit"><LoaderCircle v-if="sending" class="spin" :size="18" /><ScanLine v-else :size="18" />{{ sending ? `正在上传 ${uploadProgress}%` : '开始检测' }}<ArrowUpRight v-if="!sending" :size="17" /></button>
            <p class="local-note">文件在本地服务处理 · 完成后可删除记录</p>
          </section>

          <section class="result-panel panel">
            <div class="panel-heading"><span class="step">02</span><h2>检测结果</h2><span v-if="active" class="status-pill" :class="active.status">{{ labels[active.status] }}</span><span v-else class="panel-subtitle">OUTPUT</span></div>
            <div class="preview-toolbar"><div><span class="tiny-dot" :class="{ offline: !summary }"></span>{{ active?.filename || file?.name || '等待上传素材' }}</div><button v-if="summary && preview" class="toggle" @click="showOriginal = !showOriginal">{{ showOriginal ? '显示检测框' : '查看原图 / 原视频' }}</button></div>
            <div class="preview-area" :class="{ 'with-media': currentPreview }">
              <img v-if="currentPreview && currentKind === 'image'" :src="currentPreview" alt="图片预览与目标检测结果" />
              <video v-else-if="currentPreview" :key="currentPreview" :src="currentPreview" controls playsinline preload="metadata"></video>
              <div v-else class="preview-empty"><div class="scan-illustration"><ScanLine :size="46" :stroke-width="1" /><span></span><i></i></div><h3>{{ busy ? '正在分析画面' : '你的下一次发现，从这里开始' }}</h3><p>{{ busy ? '每一帧都在认真处理，请稍候。' : '选择一张图片或一段视频，查看目标检测结果' }}</p><div class="empty-tags"><span><Box :size="12" />目标定位</span><span>类别识别</span><span>置信度分析</span></div></div>
              <div v-if="busy" class="processing-overlay"><LoaderCircle class="spin" :size="27" /><strong>{{ sending ? `上传中 ${uploadProgress}%` : active?.phase || '等待检测' }}</strong><span v-if="active?.kind === 'video'">已处理 {{ active.processed_frames }} / {{ active.total_frames || '—' }} 帧</span><progress :value="sending ? uploadProgress : active?.progress || 0" max="100"></progress></div>
              <span v-if="summary && !showOriginal" class="preview-badge"><ScanLine :size="12" /> YOLO DETECTION</span>
            </div>
            <div class="stats"><div><span>检测目标{{ active?.kind === 'video' ? '（逐帧累计）' : '' }}</span><strong>{{ summary?.num_detections ?? '—' }}<small>个</small></strong></div><div><span>识别类别</span><strong>{{ summary ? Object.keys(summary.class_counts).length : '—' }}<small>类</small></strong></div><div><span>{{ active?.kind === 'video' ? '平均单帧推理' : '推理耗时' }}</span><strong>{{ summary?.inference_time_ms ?? '—' }}<small>ms</small></strong></div></div>
            <div class="result-footer"><span><Check :size="14" /> {{ summary ? '检测已完成，结果可下载' : '完成检测后可下载标注文件和 JSON' }}</span><div><a v-if="summary" class="download-button" :href="active.json_url + '?download=true'"><Download :size="14" />JSON</a><a v-if="summary" class="download-button primary" :href="active.result_url + '?download=true'"><Download :size="14" />{{ active.kind === 'image' ? '标注图片' : '标注视频' }}</a></div></div>
          </section>
        </div>

        <div v-if="error || active?.error" class="error-banner" role="alert"><AlertCircle :size="18" />{{ error || active.error }}</div>
        <section v-if="summary" class="panel details"><div class="panel-heading"><span class="step">03</span><h2>识别详情</h2><span class="panel-subtitle">{{ active.kind === 'video' ? '逐帧完整坐标请下载 JSON' : 'BOUNDING BOXES' }}</span></div><div class="class-chips"><span v-for="(count, label) in summary.class_counts" :key="label">{{ label }} <b>{{ count }}</b></span><p v-if="!Object.keys(summary.class_counts).length">未发现符合阈值的目标，可降低置信度后重新检测。</p></div><div v-if="summary.detections?.length" class="table-scroll"><table><thead><tr><th>目标类别</th><th>置信度</th><th>检测框坐标 [x1, y1, x2, y2]</th></tr></thead><tbody><tr v-for="(item,index) in summary.detections" :key="index"><td><span class="table-dot"></span>{{ item.label }}</td><td>{{ (item.confidence * 100).toFixed(1) }}%</td><td class="coordinates">{{ item.bbox.join(', ') }}</td></tr></tbody></table></div><p class="detail-note">{{ active.kind === 'video' ? '目标数为所有帧的检测框累计数，不代表独立对象数量。输出视频不含音轨。' : '坐标单位为像素，原点位于左上角；图片按 EXIF 方向校正后检测。' }} 本次使用 confidence={{ active.confidence }}，IoU={{ active.iou }}。</p></section>
        <footer><span>YOLO Studio <span class="footer-divider">/</span> 看见画面背后的信息</span><a href="https://docs.ultralytics.com/models/yolov8/" target="_blank" rel="noreferrer">Powered by Ultralytics <ArrowUpRight :size="12" /></a></footer>
      </main>
    </div>
  </div>
</template>
