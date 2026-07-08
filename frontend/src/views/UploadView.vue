<template>
  <div class="upload-page">
    <header class="hero">
      <div class="hero-text">
        <h1>上传识别</h1>
        <p>选择算法 → 填写元数据 → 上传文件, 提交后将自动进入识别队列</p>
      </div>
      <div class="hero-actions">
        <el-button :icon="RefreshIcon" @click="loadAlgorithms" :loading="loadingAlgos">刷新算法</el-button>
      </div>
    </header>

    <div v-if="lastResult" class="result-banner">
      <div class="result-icon"><el-icon><CircleCheckFilled /></el-icon></div>
      <div class="result-body">
        <strong>提交成功 · 记录 #{{ lastResult.record_id }}</strong>
        <p>状态: <code>{{ lastResult.status }}</code> · 状态 URL: <code>{{ lastResult.status_url }}</code></p>
      </div>
      <div class="result-actions">
        <el-button type="primary" :icon="DataLineIcon" @click="goDashboard">查看仪表盘</el-button>
        <el-button :icon="PlusIcon" @click="onReset">再传一张</el-button>
      </div>
    </div>

    <div class="upload-grid">
      <div class="upload-col">
        <article class="card">
          <header class="card-header">
            <div class="card-step">1</div>
            <div>
              <h2>选择算法</h2>
              <p class="muted small">仅显示已启用的算法 · 当前 {{ algorithms.length }} 个可选</p>
            </div>
          </header>
          <div v-if="loadingAlgos" class="algo-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载算法列表…</span>
          </div>
          <div v-else-if="algorithms.length === 0" class="algo-empty">
            <el-icon><WarningFilled /></el-icon>
            <span>暂无可用算法, 请到 <router-link to="/settings">系统设置</router-link> 启用一个</span>
          </div>
          <div v-else class="algo-cards">
            <button
              v-for="a in algorithms"
              :key="a.code"
              type="button"
              :class="['algo-pick', { selected: form.algorithmCode === a.code }]"
              :disabled="!a.is_active"
              @click="form.algorithmCode = a.code"
            >
              <div class="algo-pick-top">
                <code class="algo-pick-code">{{ a.code }}</code>
                <span v-if="form.algorithmCode === a.code" class="algo-pick-check">
                  <el-icon><Check /></el-icon>
                </span>
              </div>
              <h3>{{ a.name }}</h3>
              <div class="algo-pick-meta">
                <span :class="['engine-badge', 'engine-' + a.engine_type]">
                  <span class="engine-dot"></span>
                  {{ engineTypeLabel(a.engine_type) }}
                </span>
                <span v-if="a.category" class="algo-pick-cat">{{ a.category }}</span>
              </div>
              <p v-if="a.description" class="algo-pick-desc">{{ a.description }}</p>
            </button>
          </div>
        </article>

        <article class="card">
          <header class="card-header">
            <div class="card-step">2</div>
            <div>
              <h2>填写元数据</h2>
              <p class="muted small">选填, 便于后续按资产 / 巡检员筛选</p>
            </div>
          </header>
          <div class="form-grid">
            <div class="form-field">
              <label>资产 ID</label>
              <el-input v-model="form.assetId" placeholder="如 BJ-SUBSTATION-001" clearable>
                <template #prefix><el-icon><Location /></el-icon></template>
              </el-input>
            </div>
            <div class="form-field">
              <label>巡检员 ID</label>
              <el-input v-model="form.inspectorId" placeholder="如 INSP-001 (留空使用默认)" clearable>
                <template #prefix><el-icon><User /></el-icon></template>
              </el-input>
            </div>
          </div>
        </article>
      </div>

      <div class="upload-col">
        <article class="card">
          <header class="card-header">
            <div class="card-step">3</div>
            <div class="card-header-flex">
              <div>
                <h2>上传文件</h2>
                <p class="muted small">支持 jpg / png / mp4 · 单文件最大 20MB</p>
              </div>
              <el-radio-group v-model="uploadMode" size="small" class="upload-mode">
                <el-radio-button label="independent">独立</el-radio-button>
                <el-radio-button label="joint">
                  <el-icon style="margin-right: 4px; vertical-align: middle;"><Connection /></el-icon>联合
                </el-radio-button>
              </el-radio-group>
            </div>
          </header>
          <div
            :class="['drop-zone', { 'has-file': fileList.length > 0, dragover: isDragover }]"
            @dragover.prevent="isDragover = true"
            @dragleave.prevent="isDragover = false"
            @drop.prevent="onDrop"
          >
            <el-upload
              v-if="fileList.length === 0"
              :auto-upload="false"
              :multiple="true"
              :limit="20"
              :show-file-list="false"
              :on-change="onFileChange"
              :on-exceed="onExceed"
              drag
              class="drop-inner"
            >
              <el-icon class="drop-icon"><UploadFilled /></el-icon>
              <div class="drop-text">点击或拖拽一个或多个文件到这里</div>
              <div v-if="uploadMode === 'joint'" class="drop-hint">联合分析 · 一次上传多张图, AI 交叉对比 · 单文件最大 20MB · 最多 20 个</div>
            <div v-else class="drop-hint">独立识别 · 每张图生成一条记录 · 单文件最大 20MB</div>
            </el-upload>
            <div v-else class="file-list">
              <div class="file-list-head">
                <span class="file-list-title">已选择 {{ fileList.length }} 个文件 · 共 {{ formatSize(totalSize) }}</span>
                <div class="file-list-actions">
                  <el-upload
                    :auto-upload="false"
                    :multiple="true"
                    :limit="20 - fileList.length"
                    :show-file-list="false"
                    :on-change="onFileChange"
                    :on-exceed="onExceed"
                    class="add-more-upload"
                  >
                    <el-button :icon="PlusIcon" size="small" text>继续添加</el-button>
                  </el-upload>
                  <el-button :icon="DeleteIcon" size="small" text type="danger" @click="removeAllFiles">全部清空</el-button>
                </div>
              </div>
              <ul class="file-items">
                <li v-for="(f, idx) in fileList" :key="f.uid || idx" class="file-item">
                  <div class="file-item-thumb">
                    <el-icon v-if="!isImageOf(f) && !isVideoOf(f)" class="file-icon"><Document /></el-icon>
                    <img v-else-if="isImageOf(f) && f.previewUrl" :src="f.previewUrl" alt="preview" />
                    <video v-else-if="isVideoOf(f) && f.previewUrl" :src="f.previewUrl" muted />
                    <el-icon v-else class="file-icon"><VideoPlay /></el-icon>
                    <span v-if="f._status === 'uploading'" class="file-item-badge uploading">上传中</span>
                    <span v-else-if="f._status === 'success'" class="file-item-badge success">✓ #{{ f._recordId }}</span>
                    <span v-else-if="f._status === 'failed'" class="file-item-badge failed" :title="f._error">失败</span>
                  </div>
                  <div class="file-item-info">
                    <strong>{{ f.name }}</strong>
                    <div class="muted small">{{ formatSize(f.size || 0) }} · {{ f.raw?.type || '未知类型' }}</div>
                    <div v-if="f._status === 'failed'" class="file-item-error">{{ f._error }}</div>
                    <div v-else-if="f._status === 'uploading' || f._status === 'compressing'" class="file-item-progress">
                      <el-progress
                        :percentage="Math.round((f._progress || 0) * 100)"
                        :stroke-width="6"
                        :show-text="false"
                        :status="f._status === 'compressing' ? 'warning' : ''"
                      />
                      <span class="file-item-progress-label">{{ f._speedLabel || '上传中…' }}</span>
                      <span v-if="f._origSize &amp;&amp; f._finalSize &amp;&amp; f._finalSize &lt; f._origSize" class="file-item-progress-meta">
                        {{ formatSize(f._origSize) }} → {{ formatSize(f._finalSize) }} (压缩)
                      </span>
                    </div>
                  </div>
                  <el-button
                    :icon="DeleteIcon"
                    text
                    type="danger"
                    size="small"
                    :disabled="f._status === 'uploading'"
                    @click="removeFile(idx)"
                  >移除</el-button>
                </li>
              </ul>
            </div>
          </div>
        </article>

        <article class="card submit-card">
          <div class="submit-summary">
            <div class="summary-row">
              <span class="muted">算法</span>
              <code v-if="form.algorithmCode">{{ form.algorithmCode }}</code>
              <span v-else class="muted">未选择</span>
            </div>
            <div class="summary-row">
              <span class="muted">文件</span>
              <span v-if="fileList.length === 0" class="muted">未上传</span>
              <span v-else>{{ fileList.length }} 个 · {{ formatSize(totalSize) }}</span>
            </div>
            <div v-if="batchResults.length > 0" class="summary-row">
              <span class="muted">本批</span>
              <span>
                <el-tag v-if="batchResults.length > 0" type="success" size="small">{{ batchResults.length }} 条记录</el-tag>
              </span>
            </div>
          </div>
          <el-button
            type="primary"
            size="large"
            :icon="PromotionIcon"
            :loading="uploading"
            :disabled="!canSubmit"
            class="submit-btn"
            @click="onSubmit"
          >{{ uploading ? '提交中…' : '提交识别' }}</el-button>
        </article>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRecordsStore } from '../stores/records'
import { ElMessage, type UploadFile, type UploadRawFile } from 'element-plus'
import { compressImage } from '../composables/useImageCompress'
import { tusUpload } from '../composables/useTusUpload'
import {
  Check, CircleCheckFilled, Connection, DataLine, Delete, Document, Loading, Location,
  Plus, Promotion, Refresh, UploadFilled, User, VideoPlay, WarningFilled,
} from '@element-plus/icons-vue'

const RefreshIcon = Refresh
const DeleteIcon = Delete
const PlusIcon = Plus
const PromotionIcon = Promotion
const DataLineIcon = DataLine

const store = useRecordsStore()
const router = useRouter()

const form = reactive({ algorithmCode: '', assetId: '', inspectorId: '' })
const uploadMode = ref<'independent' | 'joint'>('joint')  // 默认联合分析
interface QueuedFile extends UploadFile {
  previewUrl?: string | null
  _status?: 'pending' | 'compressing' | 'uploading' | 'success' | 'failed'
  _recordId?: number
  _error?: string
  _progress?: number // 0-1
  _speedLabel?: string // (M2 上传相关)
  _origSize?: number // (M2 上传相关)
  _finalSize?: number // (M2 上传相关)
}
const fileList = ref<QueuedFile[]>([])
const uploading = ref(false)
// M2 上传相关: ≥1MB 走 TUS, 给图片和视频都有真实的 XHR 进度反馈
// 压缩后的图片大小 ~500KB-1MB, 1MB 阈值可以保证压缩后也走 TUS
const TUS_THRESHOLD = 1 * 1024 * 1024
const lastResult = ref<{ record_id: number; status: string; status_url: string } | null>(null)
const batchResults = ref<{ record_id: number; status: string; file: string }[]>([])
const loadingAlgos = ref(false)
const isDragover = ref(false)

const algorithms = computed(() => store.algorithms)
const canSubmit = computed(() => !!form.algorithmCode && fileList.value.length > 0 && fileList.value.some((f) => !!f.raw))
const totalSize = computed(() => fileList.value.reduce((acc, f) => acc + (f.size || 0), 0))
function isImageOf(f: QueuedFile): boolean { return (f.raw?.type || '').startsWith('image/') }
function isVideoOf(f: QueuedFile): boolean { return (f.raw?.type || '').startsWith('video/') }

function engineTypeLabel(t: string): string {
  const m: Record<string, string> = { cloud_api: '云 API', mock: 'Mock', hikvision_brain: '海康超脑', local_model: '本地模型', multimodal_llm: '多模态 LLM' }
  return m[t] || t
}
function formatSize(n: number): string {
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  return (n / 1024 / 1024).toFixed(2) + ' MB'
}
async function loadAlgorithms() {
  loadingAlgos.value = true
  try { await store.fetchAlgorithms() } finally { loadingAlgos.value = false }
}
onMounted(() => {
  if (store.algorithms.length === 0) loadAlgorithms()
  if (!form.inspectorId) form.inspectorId = localStorage.getItem('inspector_id') || 'WEB-DEMO-USER'
})
function setPreview(f: QueuedFile): QueuedFile {
  if (f.previewUrl) URL.revokeObjectURL(f.previewUrl)
  f.previewUrl = f.raw ? URL.createObjectURL(f.raw) : null
  return f
}
function wrapRaw(f: File): QueuedFile {
  const wrapped: any = { name: f.name, size: f.size, type: f.type, raw: f, _status: 'pending' }
  return setPreview(wrapped)
}
function onFileChange(f: UploadFile | UploadFile[]) {
  const incoming = Array.isArray(f) ? f : [f]
  const wrapped = incoming
    .map((it) => (it.raw ? wrapRaw(it.raw) : null))
    .filter((x): x is QueuedFile => !!x)
  fileList.value = [...fileList.value, ...wrapped]
}
function onExceed() {
  ElMessage.warning(`单次最多 20 个文件, 已达上限`)
}
function onDrop(e: DragEvent) {
  isDragover.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  if (files.length === 0) return
  const wrapped = files.map(wrapRaw)
  fileList.value = [...fileList.value, ...wrapped]
}
function removeFile(idx: number) {
  const f = fileList.value[idx]
  if (!f) return
  if (f.previewUrl) URL.revokeObjectURL(f.previewUrl)
  fileList.value.splice(idx, 1)
}
function removeAllFiles() {
  fileList.value.forEach((f) => { if (f.previewUrl) URL.revokeObjectURL(f.previewUrl) })
  fileList.value = []
}
function onReset() { form.algorithmCode = ''; form.assetId = ''; removeAllFiles(); lastResult.value = null; batchResults.value = [] }
async function onSubmit() {
  if (!form.algorithmCode) return ElMessage.warning('请选择算法')
  const pending = fileList.value.filter((f) => !!f.raw && f._status !== 'success')
  if (pending.length === 0) return ElMessage.warning('请选择文件')
  // 独立模式现已支持多文件并行上传, 每个文件生成一条记录
  if (form.inspectorId) localStorage.setItem('inspector_id', form.inspectorId)
  uploading.value = true
  batchResults.value = []
  let successCount = 0
  let failCount = 0
  // 联合分析模式 + 多文件: 一次调用 batch 端点, 一条记录
  if (uploadMode.value === 'joint' && pending.length > 1) {
    // 联合模式下, 所有文件都立即标记为 "上传中", 避免多图只能看到第一个在跑
    for (const f of pending) {
      f._status = 'uploading'
      f._progress = 0
      f._speedLabel = '联合上传中...'
      f._error = undefined
    }
    try {
      const meta: Record<string, any> = {
        filename: pending[0].name,
        is_batch: true,
      }
      if (form.assetId) meta.asset_id = form.assetId
      if (form.inspectorId) meta.inspector_id_hint = form.inspectorId
      const files = pending.map((f) => f.raw as File)
      const r: any = await store.uploadBatch(form.algorithmCode, files, meta)
      // 所有文件都标记为成功, batch 只生成一条记录
      for (const f of pending) {
        f._status = 'success'
        f._recordId = r.record_id
        f._progress = 1
        f._speedLabel = '完成'
      }
      batchResults.value.push({ record_id: r.record_id, status: r.status, file: `${pending.length} 个文件 (联合分析)` })
      successCount = pending.length
      ElMessage.success(`联合分析已提交 · 记录 #${r.record_id} · 包含 ${pending.length} 个文件`)
    } catch (e: any) {
      const errMsg = e?.response?.data?.detail?.message || e?.message || '上传失败'
      for (const f of pending) {
        f._status = 'failed'
        f._error = errMsg
        f._speedLabel = '失败'
      }
      // 联合分析失败时, 回退到独立模式逐个上传
      ElMessage.warning('联合分析失败, 自动回退为独立模式逐个上传')
      uploading.value = false
      return onSubmitIndependent(pending)
    }
    uploading.value = false
    return
  }
  // 独立模式 或 单文件: 逐个上传
  return onSubmitIndependent(pending)
}

async function onSubmitIndependent(pending: QueuedFile[]) {
  uploading.value = true

  // 提交前先把所有待上传文件的状态刷成 "上传中", UI 上每个文件都立刻有进度反馈
  for (const f of pending) {
    f._error = undefined
    f._progress = 0
    f._origSize = f.size || 0
    f._status = 'uploading'
    f._speedLabel = '等待上传...'
  }

  // 并行上传: 每个文件独立压缩 / TUS / 直接 multipart, 互不阻塞
  // 单个文件失败不会拖垮其他文件
  const results = await Promise.allSettled(pending.map((f) => uploadOneIndependent(f)))

  let successCount = 0
  let failCount = 0
  for (let i = 0; i < pending.length; i++) {
    const r = results[i]
    const f = pending[i]
    if (r.status === 'fulfilled') {
      successCount++
    } else {
      failCount++
      const e: any = r.reason
      if (f._status !== 'failed') {
        f._status = 'failed'
        f._error = e?.response?.data?.detail?.message || e?.message || '上传失败'
        f._speedLabel = '失败'
      }
    }
  }
  uploading.value = false
  if (successCount > 0 && failCount === 0) {
    ElMessage.success(`全部 ${successCount} 个文件上传成功`)
  } else if (successCount > 0 && failCount > 0) {
    ElMessage.warning(`${successCount} 成功, ${failCount} 失败`)
  } else if (failCount > 0) {
    ElMessage.error(`全部 ${failCount} 个文件上传失败`)
  }
}

/** 单个文件上传: 压缩 -> 按大小走 TUS 或 multipart, 抛错由 Promise.allSettled 兜底 */
async function uploadOneIndependent(f: QueuedFile) {
  let fileToUpload = f.raw as File
  if ((f.raw?.type || '').startsWith('image/')) {
    f._status = 'compressing'
    f._speedLabel = '压缩中...'
    const c = await compressImage(f.raw as File, {
      onProgress: ({ stage }) => {
        f._speedLabel = stage === 'loading' ? '加载中...' : (stage === 'compressing' ? '压缩中...' : (stage === 'skipped' ? '已跳过' : '完成'))
      },
    })
    fileToUpload = c.file
    f._finalSize = c.compressedSize
    if (c.compressed) {
      ElMessage.info(`图片已压缩: ${formatSize(c.originalSize)} → ${formatSize(c.compressedSize)}`)
    }
  }

  const meta: Record<string, any> = { filename: f.name }
  if (form.assetId) meta.asset_id = form.assetId
  if (form.inspectorId) meta.inspector_id_hint = form.inspectorId

  if (fileToUpload.size >= TUS_THRESHOLD) {
    f._status = 'uploading'
    f._speedLabel = '上传中...'
    const tusMeta = {
      algorithm_code: form.algorithmCode,
      inspector_id: form.inspectorId || 'WEB-DEMO-USER',
      asset_id: form.assetId || '',
    }
    const { sessionId } = await tusUpload(fileToUpload, {
      endpoint: `${window.location.origin}/api/v1/uploads`,
      metadata: tusMeta,
      onProgress: (frac) => {
        f._progress = frac
        const pct = Math.max(0, Math.min(100, Math.round((frac || 0) * 100)))
        f._speedLabel = `上传中 ${pct}%`
      },
      onStatus: (st) => {
        if (st === 'resuming') f._speedLabel = '断点续传...'
      },
    })
    f._speedLabel = '建立记录...'
    const r: { record_id: number; status: string; status_url: string } = await store.finalizeFromTus(form.algorithmCode, sessionId, meta)
    f._status = 'success'
    f._recordId = r.record_id
    f._progress = 1
    f._speedLabel = '完成'
    batchResults.value.push({ record_id: r.record_id, status: 'PENDING', file: f.name })
    return r
  }

  f._status = 'uploading'
  f._speedLabel = '上传中...'
  // 200ms 轮询兜底, 即便浏览器没触发 onUploadProgress, bar 也会缓慢前进
  const pollTimer = setInterval(() => {
    if (f._status !== 'uploading') return
    if ((f._progress || 0) < 0.95) {
      f._progress = Math.min(0.95, (f._progress || 0) + 0.02)
      const pct = Math.round((f._progress || 0) * 100)
      f._speedLabel = `上传中 ${pct}%`
    }
  }, 200)
  try {
    const r: { record_id: number; status: string; status_url: string } = await store.uploadFile(form.algorithmCode, fileToUpload, meta, (e) => {
      if (e.lengthComputable && e.total) {
        f._progress = e.loaded / e.total
        const pct = Math.max(0, Math.min(100, Math.round(f._progress * 100)))
        f._speedLabel = `上传中 ${pct}% · ${formatSize(e.loaded)} / ${formatSize(e.total)}`
      } else {
        f._speedLabel = `上传中... (${formatSize(e.loaded)})`
      }
    })
    f._status = 'success'
    f._recordId = r.record_id
    f._progress = 1
    f._speedLabel = '完成'
    batchResults.value.push({ record_id: r.record_id, status: 'PENDING', file: f.name })
    return r
  } finally {
    clearInterval(pollTimer)
  }
}

function goDashboard() { router.push('/') }
</script>

<style scoped>
.upload-page { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; color: #0f172a; max-width: 1280px; margin: 0 auto; }
.hero { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 20px; }
.hero-text h1 { margin: 0 0 6px; font-size: 26px; font-weight: 700; letter-spacing: -0.01em; }
.hero-text p { margin: 0; font-size: 13.5px; color: #64748b; }
.hero-actions { display: flex; gap: 8px; }
.result-banner { display: flex; align-items: center; gap: 16px; padding: 16px 20px; background: linear-gradient(135deg, #f0fdf4, #ecfdf5); border: 1px solid #bbf7d0; border-radius: 14px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
.result-icon { width: 40px; height: 40px; border-radius: 50%; background: #10b981; color: #fff; display: grid; place-items: center; font-size: 22px; flex-shrink: 0; }
.result-body { flex: 1; min-width: 0; }
.result-body strong { display: block; font-size: 14.5px; color: #065f46; font-weight: 600; }
.result-body p { margin: 4px 0 0; font-size: 12.5px; color: #047857; }
.result-body code { background: #fff; padding: 1px 6px; border-radius: 4px; font-size: 12px; }
.result-actions { display: flex; gap: 8px; flex-shrink: 0; }
.upload-grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 16px; }
.upload-col { display: flex; flex-direction: column; gap: 16px; }
.card { background: #fff; border: 1px solid #eef2f6; border-radius: 14px; padding: 20px 22px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
.card-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid #f1f5f9; }
.card-step { width: 28px; height: 28px; border-radius: 8px; background: linear-gradient(135deg, #6366f1, #4338ca); color: #fff; font-size: 13px; font-weight: 700; display: grid; place-items: center; flex-shrink: 0; }
.card-header-flex { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex: 1; }
.card-header h2 { margin: 0 0 2px; font-size: 15px; font-weight: 600; color: #0f172a; }
.card-header p { margin: 0; }
.algo-loading, .algo-empty { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 40px 0; color: #94a3b8; font-size: 13.5px; }
.algo-empty a { color: #4f46e5; text-decoration: underline; }
.algo-empty .el-icon { color: #f59e0b; }
.algo-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.algo-pick { text-align: left; background: #fff; border: 1.5px solid #e2e8f0; border-radius: 12px; padding: 12px 14px; cursor: pointer; transition: all 0.15s ease; display: flex; flex-direction: column; gap: 6px; font-family: inherit; }
.algo-pick:hover:not(:disabled) { border-color: #c7d2fe; background: #f5f3ff; transform: translateY(-1px); }
.algo-pick.selected { border-color: #6366f1; background: linear-gradient(135deg, #eef2ff, #f5f3ff); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12); }
.algo-pick:disabled { opacity: 0.5; cursor: not-allowed; }
.algo-pick-top { display: flex; align-items: center; justify-content: space-between; }
.algo-pick-code { font-family: ui-monospace, monospace; font-size: 11.5px; font-weight: 600; background: #f1f5f9; color: #475569; padding: 2px 7px; border-radius: 5px; }
.algo-pick-check { width: 20px; height: 20px; border-radius: 50%; background: #6366f1; color: #fff; display: grid; place-items: center; font-size: 12px; }
.algo-pick h3 { margin: 0; font-size: 13.5px; font-weight: 600; color: #0f172a; }
.algo-pick-meta { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
.algo-pick-cat { font-size: 11.5px; color: #94a3b8; }
.algo-pick-desc { margin: 4px 0 0; font-size: 12px; color: #64748b; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.engine-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px; border-radius: 999px; font-size: 11px; font-weight: 600; border: 1px solid; }
.engine-dot { width: 5px; height: 5px; border-radius: 50%; }
.engine-cloud_api { color: #4f46e5; background: #eef2ff; border-color: #e0e7ff; }
.engine-cloud_api .engine-dot { background: #6366f1; }


.engine-hikvision_brain { color: #b45309; background: #fffbeb; border-color: #fde68a; }
.engine-hikvision_brain .engine-dot { background: #f59e0b; }
.engine-local_model { color: #0e7490; background: #ecfeff; border-color: #cffafe; }
.engine-local_model .engine-dot { background: #06b6d4; }
.engine-multimodal_llm { color: #6d28d9; background: #f5f3ff; border-color: #ddd6fe; }
.engine-multimodal_llm .engine-dot { background: #8b5cf6; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.form-field { display: flex; flex-direction: column; gap: 6px; }
.form-field label { font-size: 12.5px; font-weight: 500; color: #475569; }
.form-field :deep(.el-input__wrapper) { background: #f8fafc; box-shadow: 0 0 0 1px #e2e8f0 inset; border-radius: 9px; }
.form-field :deep(.el-input__wrapper):hover { box-shadow: 0 0 0 1px #cbd5e1 inset; }
.form-field :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #6366f1 inset, 0 0 0 3px rgba(99, 102, 241, 0.1); }
.form-field :deep(.el-input__prefix-inner .el-icon) { color: #94a3b8; font-size: 14px; }
.drop-zone { border: 2px dashed #cbd5e1; border-radius: 12px; background: #f8fafc; transition: all 0.15s ease; min-height: 220px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.drop-zone.dragover { border-color: #6366f1; background: #eef2ff; }
.drop-inner { width: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 36px 20px; text-align: center; }
.drop-inner :deep(.el-upload-dragger) { background: transparent; border: 0; padding: 0; width: 100%; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.drop-icon { font-size: 38px; color: #94a3b8; }
.drop-text { font-size: 14px; color: #475569; font-weight: 500; }
.drop-hint { font-size: 12px; color: #94a3b8; }
.file-list { width: 100%; display: flex; flex-direction: column; }
.file-list-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid #eef2f6; background: #f8fafc; }
.file-list-title { font-size: 12.5px; font-weight: 500; color: #475569; }
.file-list-actions { display: flex; gap: 4px; }
.add-more-upload :deep(.el-upload) { display: inline-block; }
.file-items { list-style: none; padding: 8px; margin: 0; max-height: 320px; overflow-y: auto; }
.file-item { display: flex; align-items: center; gap: 12px; padding: 8px 10px; border-radius: 8px; transition: background 0.12s ease; }
.file-item:hover { background: #f8fafc; }
.file-item-thumb { width: 48px; height: 48px; border-radius: 8px; background: #f1f5f9; display: grid; place-items: center; overflow: hidden; flex-shrink: 0; position: relative; border: 1px solid #e2e8f0; }
.file-item-thumb img, .file-item-thumb video { width: 100%; height: 100%; object-fit: cover; }
.file-item-thumb .file-icon { font-size: 22px; color: #94a3b8; }
.file-item-badge { position: absolute; bottom: -4px; right: -4px; font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 6px; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.15); }
.file-item-badge.uploading { background: #fef3c7; color: #92400e; }
.file-item-badge.success { background: #dcfce7; color: #166534; }
.file-item-badge.failed { background: #fee2e2; color: #991b1b; }
.file-item-info { flex: 1; min-width: 0; }
.file-item-info strong { display: block; font-size: 13px; color: #0f172a; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-item-error { font-size: 11.5px; color: #b91c1c; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-item-progress { display: flex; align-items: center; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.file-item-progress :deep(.el-progress) { flex: 1 1 140px; min-width: 100px; }
.file-item-progress-label { font-size: 11.5px; color: #6366f1; font-weight: 500; }
.file-item-progress-meta { font-size: 11px; color: #16a34a; font-weight: 500; }
.file-item-uploading { color: #d97706; font-size: 11.5px; margin-top: 2px; }
.file-preview { display: flex; align-items: center; gap: 16px; padding: 16px; width: 100%; background: #fff; }
.file-thumb { width: 96px; height: 96px; border-radius: 10px; background: #f1f5f9; display: grid; place-items: center; overflow: hidden; flex-shrink: 0; }
.file-thumb img, .file-thumb video { width: 100%; height: 100%; object-fit: cover; }
.file-icon { font-size: 36px; color: #94a3b8; }
.file-info { flex: 1; min-width: 0; }
.file-info strong { display: block; font-size: 13.5px; color: #0f172a; word-break: break-all; margin-bottom: 4px; }
.submit-card { display: flex; flex-direction: column; gap: 14px; }
.submit-summary { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; background: #f8fafc; border-radius: 10px; border: 1px solid #f1f5f9; }
.summary-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 13px; }
.summary-row code { font-family: ui-monospace, monospace; font-size: 12px; background: #fff; padding: 1px 7px; border-radius: 5px; color: #4338ca; }
.submit-btn { height: 48px; font-size: 15px; font-weight: 600; background: linear-gradient(135deg, #6366f1, #4338ca); border: 0; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25); }
.submit-btn:hover { background: linear-gradient(135deg, #4f46e5, #3730a3); transform: translateY(-1px); box-shadow: 0 6px 16px rgba(79, 70, 229, 0.35); }
.submit-btn:disabled { background: #cbd5e1; box-shadow: none; transform: none; }
.muted { color: #94a3b8; }
.small { font-size: 12px; }
@media (max-width: 1000px) { .upload-grid { grid-template-columns: 1fr; } .algo-cards { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .form-grid { grid-template-columns: 1fr; } .hero { flex-direction: column; align-items: flex-start; } .result-banner { flex-direction: column; align-items: flex-start; } .result-actions { width: 100%; } }
</style>
