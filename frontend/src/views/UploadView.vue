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
            <div>
              <h2>上传文件</h2>
              <p class="muted small">支持 jpg / png / mp4 · 单文件最大 20MB</p>
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
              :limit="1"
              :show-file-list="false"
              :on-change="onFileChange"
              drag
              class="drop-inner"
            >
              <el-icon class="drop-icon"><UploadFilled /></el-icon>
              <div class="drop-text">点击或拖拽文件到这里</div>
              <div class="drop-hint">支持 jpg / png / mp4 · 最大 20MB</div>
            </el-upload>
            <div v-else class="file-preview">
              <div class="file-thumb">
                <el-icon v-if="!previewUrl" class="file-icon"><Document /></el-icon>
                <img v-else-if="isImage" :src="previewUrl" alt="preview" />
                <video v-else-if="isVideo" :src="previewUrl" controls />
                <el-icon v-else class="file-icon"><VideoPlay /></el-icon>
              </div>
              <div class="file-info">
                <strong>{{ fileList[0].name }}</strong>
                <div class="muted small">{{ formatSize(fileList[0].size || 0) }} · {{ fileList[0].raw?.type || '未知类型' }}</div>
                <el-button :icon="DeleteIcon" text type="danger" size="small" @click="removeFile">移除</el-button>
              </div>
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
              <span v-if="fileList[0]">{{ fileList[0].name }}</span>
              <span v-else class="muted">未上传</span>
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
import {
  Check, CircleCheckFilled, DataLine, Delete, Document, Loading, Location,
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
const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const lastResult = ref<{ record_id: number; status: string; status_url: string } | null>(null)
const loadingAlgos = ref(false)
const isDragover = ref(false)
const previewUrl = ref<string | null>(null)

const algorithms = computed(() => store.algorithms)
const canSubmit = computed(() => !!form.algorithmCode && fileList.value.length > 0 && !!fileList.value[0]?.raw)
const isImage = computed(() => (fileList.value[0]?.raw?.type || '').startsWith('image/'))
const isVideo = computed(() => (fileList.value[0]?.raw?.type || '').startsWith('video/'))

function engineTypeLabel(t: string): string {
  const m: Record<string, string> = { cloud_api: '云 API', mock: 'Mock', hikvision_brain: '海康超脑', local_model: '本地模型' }
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
function onFileChange(f: UploadFile) { fileList.value = [f]; setPreview(f) }
function onDrop(e: DragEvent) {
  isDragover.value = false
  const f = e.dataTransfer?.files?.[0]
  if (!f) return
  const wrapped: any = { name: f.name, size: f.size, type: f.type, raw: f as UploadRawFile }
  fileList.value = [wrapped as UploadFile]; setPreview(wrapped)
}
function setPreview(f: any) {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = f.raw ? URL.createObjectURL(f.raw) : null
}
function removeFile() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = null; fileList.value = []
}
function onReset() { form.algorithmCode = ''; form.assetId = ''; removeFile(); lastResult.value = null }
async function onSubmit() {
  if (!form.algorithmCode) return ElMessage.warning('请选择算法')
  if (!fileList.value[0]?.raw) return ElMessage.warning('请选择文件')
  uploading.value = true
  try {
    if (form.inspectorId) localStorage.setItem('inspector_id', form.inspectorId)
    const meta: Record<string, any> = {}
    if (form.assetId) meta.asset_id = form.assetId
    if (form.inspectorId) meta.inspector_id_hint = form.inspectorId
    const r = await store.uploadFile(form.algorithmCode, fileList.value[0].raw, meta)
    ElMessage.success('上传成功 · 记录 #' + r.record_id)
    lastResult.value = r
  } catch { /* handled */ } finally { uploading.value = false }
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
.engine-mock { color: #047857; background: #ecfdf5; border-color: #d1fae5; }
.engine-mock .engine-dot { background: #10b981; }
.engine-hikvision_brain { color: #b45309; background: #fffbeb; border-color: #fde68a; }
.engine-hikvision_brain .engine-dot { background: #f59e0b; }
.engine-local_model { color: #0e7490; background: #ecfeff; border-color: #cffafe; }
.engine-local_model .engine-dot { background: #06b6d4; }
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
