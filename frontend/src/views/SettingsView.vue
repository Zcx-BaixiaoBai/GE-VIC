<template>
  <div class="settings-page">
    <!-- Hero header -->
    <header class="hero">
      <div class="hero-text">
        <h1>系统设置</h1>
        <p>管理识别算法与 LLM 富化服务 · 当前环境: <span class="env-tag">{{ envLabel }}</span></p>
      </div>
      <div class="hero-actions">
        <el-button :icon="RefreshIcon" @click="reloadAll" :loading="loading || llmLoading">刷新</el-button>
        <el-button type="primary" :icon="PlusIcon" @click="openCreateDialog">新增算法</el-button>
      </div>
    </header>

    <!-- Stats row -->
    <section class="stats">
      <article class="stat-card" :class="`tint-indigo`">
        <div class="stat-icon"><el-icon><Cpu /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ algorithms.length }}</div>
          <div class="stat-label">算法总数</div>
        </div>
      </article>
      <article class="stat-card" :class="`tint-emerald`">
        <div class="stat-icon"><el-icon><CircleCheck /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ activeCount }}</div>
          <div class="stat-label">已启用</div>
        </div>
      </article>
      <article class="stat-card" :class="`tint-cyan`">
        <div class="stat-icon"><el-icon><DataLine /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ cloudCount }}</div>
          <div class="stat-label">云端 API</div>
        </div>
      </article>
      <article class="stat-card" :class="`tint-amber`">
        <div class="stat-icon"><el-icon><MagicStick /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ mockCount }}</div>
          <div class="stat-label">模拟引擎</div>
        </div>
      </article>
    </section>

    <!-- Segmented tabs -->
    <nav class="segmented">
      <button
        v-for="t in tabs"
        :key="t.key"
        :class="['seg-btn', { active: activeTab === t.key }]"
        @click="activeTab = t.key"
      >
        <el-icon><component :is="t.icon" /></el-icon>
        <span>{{ t.label }}</span>
        <span v-if="t.badge" class="seg-badge">{{ t.badge }}</span>
      </button>
    </nav>

    <!-- Algorithm tab -->
    <section v-show="activeTab === 'algorithms'" class="content">
      <div class="toolbar">
        <div class="search-box">
          <el-icon><Search /></el-icon>
          <input
            v-model="searchTerm"
            type="text"
            placeholder="搜索 code 或名称..."
          />
          <button v-if="searchTerm" class="search-clear" @click="searchTerm = ''" aria-label="清除">
            <el-icon><Close /></el-icon>
          </button>
        </div>
        <div class="filter-pills">
          <button
            v-for="f in filters"
            :key="f.key"
            :class="['pill', { active: filterKey === f.key }]"
            @click="filterKey = f.key"
          >
            {{ f.label }}
            <span class="pill-count">{{ f.count }}</span>
          </button>
        </div>
      </div>

      <div v-if="filteredAlgos.length === 0 && !loading" class="empty">
        <el-icon class="empty-icon"><FolderDelete /></el-icon>
        <h3>没有匹配的算法</h3>
        <p>尝试调整搜索关键词, 或新增一个算法。</p>
      </div>

      <div v-else class="algo-grid">
        <article
          v-for="algo in filteredAlgos"
          :key="algo.code"
          class="algo-card"
          :class="{ inactive: !algo.is_active }"
        >
          <header class="algo-card-header">
            <div class="algo-card-title">
              <code class="algo-code">{{ algo.code }}</code>
              <h3>{{ algo.name }}</h3>
            </div>
            <el-switch
              v-model="algo.is_active"
              :loading="algo._toggling"
              inline-prompt
              active-text="启用"
              inactive-text="停用"
              @change="(v: boolean | string | number) => onToggleActive(algo, Boolean(v))"
            />
          </header>

          <div class="algo-card-tags">
            <span :class="['engine-badge', `engine-${algo.engine_type}`]">
              <span class="engine-dot"></span>
              {{ engineTypeLabel(algo.engine_type) }}
            </span>
            <span v-if="algo.category" class="category-pill">
              <el-icon><Folder /></el-icon>
              {{ algo.category }}
            </span>
            <span class="version-pill">v{{ algo.version }}</span>
          </div>

          <p v-if="algo.description" class="algo-desc">{{ algo.description }}</p>
          <p v-else class="algo-desc muted">暂无描述</p>

          <footer class="algo-card-footer">
            <span class="muted small">ID #{{ algo.code }}</span>
            <div class="algo-actions">
              <el-button :icon="ViewIcon" size="small" text @click="showConfig(algo)">查看配置</el-button>
              <el-button :icon="DeleteIcon" size="small" text type="danger" @click="onDelete(algo)">删除</el-button>
            </div>
          </footer>
        </article>
      </div>

      <!-- 新增算法对话框 -->
      <el-dialog
        v-model="createDialogVisible"
        title="新增算法"
        width="600"
        class="settings-dialog"
        :close-on-click-modal="false"
      >
        <el-form
          :model="createForm"
          label-width="100"
          :rules="createRules"
          ref="createFormRef"
          class="create-form"
        >
          <el-form-item label="Code" prop="code">
            <el-input v-model="createForm.code" placeholder="如: my-algo-1 (小写+数字+连字符)" />
          </el-form-item>
          <el-form-item label="名称" prop="name">
            <el-input v-model="createForm.name" placeholder="显示名称, 如: 输电线路缺陷识别" />
          </el-form-item>
          <el-form-item label="类别">
            <el-input v-model="createForm.category" placeholder="如: 供配电 / 供水 / 排水" />
          </el-form-item>
          <el-form-item label="引擎类型" prop="engine_type">
            <el-select v-model="createForm.engine_type" style="width: 100%">
              <el-option label="Mock 引擎 (本地测试)" value="mock" />
              <el-option label="Cloud API (阿里云/腾讯云等)" value="cloud_api" />
              <el-option label="海康超脑" value="hikvision_brain" />
              <el-option label="多模态 LLM (把 LLM 当识别器)" value="multimodal_llm" />
              <el-option label="本地模型" value="local_model" />
            </el-select>
          </el-form-item>
          <el-form-item label="引擎配置">
            <div class="config-form-header">
              <span class="muted small">{{ currentSchema.length }} 个字段</span>
              <el-button text :icon="showRawJson ? ViewIcon : DocumentIcon" size="small" @click="showRawJson = !showRawJson">
                {{ showRawJson ? '返回表单' : '高级: 查看/编辑 JSON' }}
              </el-button>
            </div>

            <!-- 表单模式 -->
            <div v-if="!showRawJson" class="config-fields">
              <div v-for="field in currentSchema" :key="field.key" class="config-field-row">
                <label class="config-field-label">
                  {{ field.label }}
                  <span v-if="field.sensitive" class="sensitive-tag">敏感</span>
                </label>
                <div class="config-field-control">
                  <el-input v-if="field.type === 'text'" v-model="createForm.engineConfig[field.key]" :placeholder="field.placeholder" clearable />
                  <el-input v-else-if="field.type === 'password'" v-model="createForm.engineConfig[field.key]" type="password" :placeholder="field.placeholder || '输入后写入数据库'" show-password clearable />
                  <el-input-number v-else-if="field.type === 'number'" v-model="createForm.engineConfig[field.key]" :min="field.min" :max="field.max" :step="field.step || 1" :placeholder="String(field.default)" controls-position="right" style="width: 100%" />
                  <div v-else-if="field.type === 'slider'" class="slider-wrap">
                    <el-slider v-model="createForm.engineConfig[field.key]" :min="field.min || 0" :max="field.max || 1" :step="field.step || 0.1" show-input :show-input-controls="false" />
                    <code class="slider-value">{{ Number(createForm.engineConfig[field.key]).toFixed(1) }}</code>
                  </div>
                  <el-input v-else-if="field.type === 'textarea'" v-model="createForm.engineConfig[field.key]" type="textarea" :rows="3" :placeholder="field.placeholder" />
                  <el-select v-else-if="field.type === 'select' && field.options" v-model="createForm.engineConfig[field.key]" style="width: 100%">
                    <el-option v-for="opt in field.options" :key="opt.value" :label="opt.label" :value="opt.value" />
                  </el-select>
                  <span v-if="field.hint" class="form-hint">{{ field.hint }}</span>
                </div>
              </div>
              <div v-if="currentSchema.length === 0" class="muted small">此引擎类型暂无配置项, 使用默认参数</div>
            </div>

            <!-- 原始 JSON 模式 -->
            <el-input
              v-else
              v-model="engineConfigJsonStr"
              type="textarea"
              :rows="8"
              class="json-input"
              @blur="syncJsonToConfig"
            />
            <span v-if="showRawJson" class="form-hint">直接编辑 JSON, 失焦后自动同步到表单</span>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="creating" @click="onCreate">创建算法</el-button>
        </template>
      </el-dialog>

      <!-- 配置详情对话框 -->
      <el-dialog
        v-model="configDialogVisible"
        :title="`算法配置: ${selectedAlgo?.code || ''}`"
        width="720"
        class="settings-dialog"
      >
        <div v-if="selectedAlgo" v-loading="configLoading">
          <el-descriptions :column="2" border class="info-table">
            <el-descriptions-item label="Code">
              <code>{{ selectedAlgo.code }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="版本">v{{ selectedAlgo.version }}</el-descriptions-item>
            <el-descriptions-item label="名称">{{ selectedAlgo.name }}</el-descriptions-item>
            <el-descriptions-item label="类别">{{ selectedAlgo.category || '-' }}</el-descriptions-item>
            <el-descriptions-item label="引擎类型" :span="2">
              <span :class="['engine-badge', `engine-${selectedAlgo.engine_type}`]">
                <span class="engine-dot"></span>
                {{ engineTypeLabel(selectedAlgo.engine_type) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="状态" :span="2">
              <span :class="['status-tag', selectedAlgo.is_active ? 'active' : 'inactive']">
                <span class="status-dot"></span>
                {{ selectedAlgo.is_active ? '已启用' : '已停用' }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="描述" :span="2">
              {{ selectedAlgo.description || '—' }}
            </el-descriptions-item>
          </el-descriptions>

          <h4 class="json-title">引擎配置 <span class="muted small">engine_config</span></h4>
          <pre class="json-block">{{ formatJson(selectedAlgo.engine_config) }}</pre>

          <h4 v-if="selectedAlgo.request_schema" class="json-title">请求 schema <span class="muted small">request_schema</span></h4>
          <pre v-if="selectedAlgo.request_schema" class="json-block">{{ formatJson(selectedAlgo.request_schema) }}</pre>
        </div>
      </el-dialog>
    </section>

    <!-- LLM tab -->
    <section v-show="activeTab === 'llm'" class="content">
      <div v-if="llmConfig?.mock_mode" class="banner banner-warning">
        <el-icon><WarningFilled /></el-icon>
        <div>
          <strong>演示模式 (LLM_MOCK_MODE=true)</strong>
          <p>LLM 客户端返回预设响应, 不调用真实 API。生产部署需关闭此开关并配置真实凭据。</p>
        </div>
      </div>

      <div class="llm-grid">
        <article class="llm-card">
          <header class="llm-card-header">
            <div>
              <h2>富化服务配置</h2>
              <p class="muted small">只读展示, 实际值由环境变量注入</p>
            </div>
            <el-button :icon="RefreshIcon" text @click="loadLLM">刷新</el-button>
          </header>

          <div v-if="llmConfig" class="config-fields">
            <div class="config-field">
              <div class="field-label"><el-icon><Connection /></el-icon> Base URL</div>
              <code class="field-value mono">{{ llmConfig.base_url }}</code>
            </div>
            <div class="config-field">
              <div class="field-label"><el-icon><Cpu /></el-icon> Model</div>
              <div class="field-value">{{ llmConfig.model }}</div>
            </div>
            <div class="config-field">
              <div class="field-label"><el-icon><Sort /></el-icon> Max Input Tokens</div>
              <div class="field-value">{{ llmConfig.max_input_tokens }}</div>
            </div>
            <div class="config-field">
              <div class="field-label"><el-icon><Sort /></el-icon> Max Output Tokens</div>
              <div class="field-value">{{ llmConfig.max_output_tokens }}</div>
            </div>
            <div class="config-field">
              <div class="field-label"><el-icon><WarningFilled /></el-icon> Mock Mode</div>
              <div class="field-value">
                <span :class="['status-tag', llmConfig.mock_mode ? 'inactive' : 'active']">
                  <span class="status-dot"></span>
                  {{ llmConfig.mock_mode ? '是 (演示模式)' : '否 (真实调用)' }}
                </span>
              </div>
            </div>
          </div>
        </article>

        <article class="llm-card">
          <header class="llm-card-header">
            <div>
              <h2>连接测试</h2>
              <p class="muted small">发送最小 prompt 验证 LLM 服务可达</p>
            </div>
          </header>

          <div class="test-area">
            <p class="test-prompt">
              <span class="test-prompt-label">PROMPT</span>
              <code>Reply with the single word: OK</code>
            </p>
            <el-button
              type="primary"
              size="large"
              :icon="ConnectionIcon"
              :loading="llmTesting"
              @click="onTestLLM"
            >
              {{ llmTestResult ? '再次测试' : '运行测试' }}
            </el-button>
          </div>

          <div v-if="llmTestResult" class="test-result" :class="llmTestResult.success ? 'success' : 'fail'">
            <header class="test-result-header">
              <el-icon class="result-icon">
                <component :is="llmTestResult.success ? CircleCheck : CircleClose" />
              </el-icon>
              <div>
                <strong>{{ llmTestResult.success ? '连接成功' : '连接失败' }}</strong>
                <p class="muted small">{{ llmTestResult.message }}</p>
              </div>
            </header>
            <dl v-if="llmTestResult.model" class="result-meta">
              <div v-if="llmTestResult.model">
                <dt>模型</dt>
                <dd>{{ llmTestResult.model }}</dd>
              </div>
              <div v-if="llmTestResult.total_tokens">
                <dt>Tokens</dt>
                <dd>
                  <span class="token-pill">in {{ llmTestResult.prompt_tokens }}</span>
                  <span class="token-pill">out {{ llmTestResult.completion_tokens }}</span>
                  <span class="token-pill total">∑ {{ llmTestResult.total_tokens }}</span>
                </dd>
              </div>
              <div v-if="llmTestResult.duration_ms">
                <dt>耗时</dt>
                <dd>{{ llmTestResult.duration_ms }} ms</dd>
              </div>
            </dl>
            <pre v-if="llmTestResult.content_preview" class="result-preview">{{ llmTestResult.content_preview }}</pre>
          </div>
        </article>
      </div>

      <div class="banner banner-info">
        <el-icon><InfoFilled /></el-icon>
        <div>
          <strong>配置方式</strong>
          <p>LLM 配置通过环境变量 (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / LLM_MOCK_MODE) 注入。修改配置需重启后端进程, 然后点击刷新查看新值。</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Cpu,
  CircleCheck,
  CircleClose,
  Close,
  Connection,
  Document,
  DataLine,
  Delete,
  Folder,
  FolderDelete,
  InfoFilled,
  MagicStick,
  Plus,
  Refresh,
  Search,
  Sort,
  View,
  WarningFilled,
} from '@element-plus/icons-vue'
import { algorithmsApi, settingsApi, type Algorithm, type LLMConfig, type LLMTestResult } from '../api/client'

interface AlgorithmWithMeta extends Algorithm { _toggling?: boolean }

const PlusIcon = Plus
const RefreshIcon = Refresh
const DocumentIcon = Document
const ViewIcon = View
const DeleteIcon = Delete
const ConnectionIcon = Connection

const activeTab = ref<'algorithms' | 'llm'>('algorithms')

const tabs = computed(() => [
  { key: 'algorithms' as const, label: '算法配置', icon: Cpu, badge: algorithms.value.length },
  { key: 'llm' as const, label: 'LLM 富化', icon: MagicStick, badge: '' },
])

const envLabel = computed(() => (llmConfig.value?.mock_mode ? '演示 (Mock)' : '生产 (真实调用)'))

// 算法管理
const algorithms = ref<AlgorithmWithMeta[]>([])
const loading = ref(false)
const searchTerm = ref('')
const filterKey = ref<'all' | 'active' | 'inactive'>('all')

const activeCount = computed(() => algorithms.value.filter((a) => a.is_active).length)
const cloudCount = computed(() => algorithms.value.filter((a) => a.engine_type === 'cloud_api').length)
const mockCount = computed(() => algorithms.value.filter((a) => a.engine_type === 'mock').length)

const filteredAlgos = computed(() => {
  const term = searchTerm.value.trim().toLowerCase()
  return algorithms.value.filter((a) => {
    if (filterKey.value === 'active' && !a.is_active) return false
    if (filterKey.value === 'inactive' && a.is_active) return false
    if (!term) return true
    return (
      a.code.toLowerCase().includes(term) ||
      (a.name || '').toLowerCase().includes(term) ||
      (a.category || '').toLowerCase().includes(term)
    )
  })
})

const filters = computed(() => [
  { key: 'all' as const, label: '全部', count: algorithms.value.length },
  { key: 'active' as const, label: '已启用', count: activeCount.value },
  { key: 'inactive' as const, label: '已停用', count: algorithms.value.length - activeCount.value },
])

// 每个引擎类型的配置字段定义 (驱动动态表单)
interface EngineFieldDef {
  key: string
  label: string
  type: 'text' | 'number' | 'slider' | 'textarea' | 'password' | 'select'
  default: any
  hint?: string
  placeholder?: string
  min?: number
  max?: number
  step?: number
  options?: Array<{ label: string; value: string }>
  sensitive?: boolean
}

const ENGINE_SCHEMAS: Record<string, EngineFieldDef[]> = {
  multimodal_llm: [
    { key: 'extract_frames', label: '视频抽帧数', type: 'number', min: 1, max: 8, step: 1, default: 3, hint: '视频上传时均匀采样的帧数 (1-8)' },
    { key: 'max_long_edge', label: '帧长边限制 (px)', type: 'number', min: 256, max: 2048, step: 64, default: 1024, hint: '抽出的帧会缩放到此长边' },
    { key: 'temperature', label: 'LLM 温度', type: 'slider', min: 0, max: 1, step: 0.1, default: 0.3, hint: '越高输出越随机' },
    { key: 'prompt', label: '系统提示词 (可选)', type: 'textarea', default: '', placeholder: '留空使用默认中文巡检 prompt', hint: '指导 LLM 输出 JSON 结构化结果的指令' },
    { key: 'user_prompt', label: '用户提示词 (可选)', type: 'textarea', default: '', placeholder: '留空使用默认' },
  ],
  cloud_api: [
    { key: 'provider', label: '厂商', type: 'select', default: 'aliyun', options: [
      { label: '阿里云视觉智能', value: 'aliyun' },
      { label: '腾讯云', value: 'tencent' },
      { label: '百度智能云', value: 'baidu' },
    ]},
    { key: 'endpoint', label: 'API 端点 URL', type: 'text', default: 'https://imagerecog.cn-shanghai.aliyuncs.com' },
    { key: 'action', label: 'API Action', type: 'text', default: 'RecognizeInsulatorDamage' },
    { key: 'access_key_id', label: 'Access Key ID', type: 'text', default: '', placeholder: 'AKID...' },
    { key: 'access_key_secret', label: 'Access Key Secret', type: 'password', default: '', sensitive: true, hint: '写入数据库前会自动剔除 secret 字段' },
    { key: 'timeout_sec', label: '超时 (秒)', type: 'number', min: 5, max: 120, step: 5, default: 30 },
  ],
  mock: [
    { key: 'delay_ms', label: '模拟耗时 (ms)', type: 'number', min: 0, max: 10000, step: 100, default: 500, hint: '识别模拟的延迟, 演示用' },
    { key: 'defects_count', label: '返回缺陷数', type: 'number', min: 0, max: 10, step: 1, default: 1 },
  ],
  hikvision_brain: [
    { key: 'endpoint', label: '海康超脑 API 地址', type: 'text', default: '', placeholder: 'https://<host>:<port>' },
    { key: 'username', label: '用户名', type: 'text', default: '' },
    { key: 'password', label: '密码', type: 'password', default: '', sensitive: true },
  ],
  local_model: [
    { key: 'endpoint', label: '推理服务 URL', type: 'text', default: 'http://localhost:8001' },
  ],
}

function buildDefaultConfig(engineType: string): Record<string, any> {
  const schema = ENGINE_SCHEMAS[engineType] || []
  const cfg: Record<string, any> = {}
  for (const f of schema) cfg[f.key] = f.default
  return cfg
}

const createDialogVisible = ref(false)
const creating = ref(false)
const createFormRef = ref()
const showRawJson = ref(false)
const createForm = ref({
  code: '',
  name: '',
  category: '',
  engine_type: 'mock',
  engineConfig: buildDefaultConfig('mock'),
})
const createRules = {
  code: [
    { required: true, message: '请输入 code', trigger: 'blur' },
    { pattern: /^[a-z0-9-]+$/, message: '只能包含小写字母、数字和连字符', trigger: 'blur' },
  ],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  engine_type: [{ required: true, message: '请选择引擎类型', trigger: 'change' }],
}

const configDialogVisible = ref(false)
const configLoading = ref(false)
const selectedAlgo = ref<Algorithm | null>(null)

async function loadAlgorithms() {
  loading.value = true
  try {
    algorithms.value = await algorithmsApi.listAll(true)
  } finally {
    loading.value = false
  }
}

function reloadAll() {
  loadAlgorithms()
  loadLLM()
}

function engineTypeLabel(t: string): string {
  const map: Record<string, string> = {
    cloud_api: '云 API',
    mock: 'Mock',
    multimodal_llm: '多模态 LLM',
    hikvision_brain: '海康超脑',
    local_model: '本地模型',
  }
  return map[t] || t
}

function formatJson(obj: any): string {
  if (!obj) return '(空)'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

async function onToggleActive(row: AlgorithmWithMeta, val: boolean) {
  row._toggling = true
  try {
    await algorithmsApi.update(row.code, { is_active: val })
    ElMessage.success(`${row.code} 已${val ? '启用' : '停用'}`)
  } catch {
    row.is_active = !val
  } finally {
    row._toggling = false
  }
}

function showConfig(row: Algorithm) {
  selectedAlgo.value = row
  configDialogVisible.value = true
}

async function onDelete(row: Algorithm) {
  try {
    await ElMessageBox.confirm(
      `确定删除算法 ${row.code}? 这将影响所有引用此算法的上传。`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  await algorithmsApi.remove(row.code)
  ElMessage.success(`已删除 ${row.code}`)
  await loadAlgorithms()
}

const currentSchema = computed<EngineFieldDef[]>(() => ENGINE_SCHEMAS[createForm.value.engine_type] || [])
const engineConfigJsonStr = ref('')

function configToJson(cfg: Record<string, any>): string {
  const cleaned: Record<string, any> = {}
  for (const [k, v] of Object.entries(cfg || {})) {
    if (v !== '' && v !== null && v !== undefined) cleaned[k] = v
  }
  return JSON.stringify(cleaned, null, 2)
}
function syncConfigToJson() {
  engineConfigJsonStr.value = configToJson(createForm.value.engineConfig)
}
function syncJsonToConfig() {
  const text = engineConfigJsonStr.value.trim()
  if (!text) {
    createForm.value.engineConfig = buildDefaultConfig(createForm.value.engine_type)
    return
  }
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      const merged: Record<string, any> = { ...buildDefaultConfig(createForm.value.engine_type), ...parsed }
      createForm.value.engineConfig = merged
    } else {
      ElMessage.error('JSON 必须是对象')
    }
  } catch (e) {
    ElMessage.error('JSON 解析失败: ' + e)
  }
}

function openCreateDialog() {
  createForm.value = {
    code: '',
    name: '',
    category: '',
    engine_type: 'mock',
    engineConfig: buildDefaultConfig('mock'),
  }
  showRawJson.value = false
  syncConfigToJson()
  createDialogVisible.value = true
}

async function onCreate() {
  if (!createFormRef.value) return
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return

  if (showRawJson.value) syncJsonToConfig()

  const engineConfig: Record<string, any> = {}
  for (const [k, v] of Object.entries(createForm.value.engineConfig || {})) {
    if (v === '' || v === null || v === undefined) continue
    engineConfig[k] = v
  }

  creating.value = true
  try {
    const created = await algorithmsApi.create({
      code: createForm.value.code,
      name: createForm.value.name,
      category: createForm.value.category || null,
      engine_type: createForm.value.engine_type,
      engine_config: engineConfig,
    })
    ElMessage.success(`已创建算法 ${created.code}`)
    createDialogVisible.value = false
    await loadAlgorithms()
  } finally {
    creating.value = false
  }
}

// LLM 配置
const llmConfig = ref<LLMConfig | null>(null)
const llmLoading = ref(false)
const llmTesting = ref(false)
const llmTestResult = ref<LLMTestResult | null>(null)

async function loadLLM() {
  llmLoading.value = true
  try {
    llmConfig.value = await settingsApi.getLLM()
  } finally {
    llmLoading.value = false
  }
}

async function onTestLLM() {
  llmTesting.value = true
  try {
    llmTestResult.value = await settingsApi.testLLM()
  } finally {
    llmTesting.value = false
  }
}

watch(() => createForm.value.engine_type, (newType) => {
  createForm.value.engineConfig = buildDefaultConfig(newType)
  if (showRawJson.value) syncConfigToJson()
})

onMounted(() => {
  loadAlgorithms()
  loadLLM()
})
</script>

<style scoped>
.settings-page {
  --tint-indigo: #6366f1;
  --tint-indigo-bg: #eef2ff;
  --tint-emerald: #10b981;
  --tint-emerald-bg: #ecfdf5;
  --tint-cyan: #06b6d4;
  --tint-cyan-bg: #ecfeff;
  --tint-amber: #f59e0b;
  --tint-amber-bg: #fffbeb;
  --tint-rose: #f43f5e;
  --tint-rose-bg: #fef2f2;
  --tint-slate: #64748b;
  --tint-slate-bg: #f1f5f9;

  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  color: #0f172a;
  max-width: 1200px;
  margin: 0 auto;
  padding: 8px 0 40px;
}

/* ---- Hero ---- */
.hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 24px;
}
.hero-text h1 {
  margin: 0 0 6px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: #0f172a;
}
.hero-text p {
  margin: 0;
  font-size: 13.5px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 8px;
}
.env-tag {
  display: inline-block;
  padding: 2px 10px;
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  color: #4f46e5;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid #e0e7ff;
}
.hero-actions {
  display: flex;
  gap: 8px;
}

/* ---- Stats ---- */
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.stat-card {
  background: #ffffff;
  border: 1px solid #eef2f6;
  border-radius: 14px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.stat-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.07);
}
.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 22px;
  flex-shrink: 0;
}
.tint-indigo .stat-icon { background: var(--tint-indigo-bg); color: var(--tint-indigo); }
.tint-emerald .stat-icon { background: var(--tint-emerald-bg); color: var(--tint-emerald); }
.tint-cyan .stat-icon { background: var(--tint-cyan-bg); color: var(--tint-cyan); }
.tint-amber .stat-icon { background: var(--tint-amber-bg); color: var(--tint-amber); }
.stat-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.01em;
  color: #0f172a;
}
.stat-label {
  margin-top: 2px;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* ---- Segmented ---- */
.segmented {
  display: inline-flex;
  padding: 4px;
  background: #f1f5f9;
  border-radius: 12px;
  margin-bottom: 20px;
  gap: 2px;
}
.seg-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: transparent;
  border: 0;
  border-radius: 9px;
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  color: #475569;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}
.seg-btn:hover { color: #0f172a; }
.seg-btn.active {
  background: #ffffff;
  color: #0f172a;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.04);
}
.seg-badge {
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 999px;
  min-width: 18px;
  text-align: center;
}
.seg-btn.active .seg-badge {
  background: #eef2ff;
  color: #4f46e5;
}

/* ---- Toolbar ---- */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0 12px;
  height: 38px;
  min-width: 280px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.search-box:focus-within {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
}
.search-box .el-icon {
  color: #94a3b8;
  font-size: 16px;
}
.search-box input {
  flex: 1;
  border: 0;
  outline: 0;
  font: inherit;
  font-size: 14px;
  color: #0f172a;
  background: transparent;
}
.search-box input::placeholder { color: #94a3b8; }
.search-clear {
  border: 0;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
}
.search-clear:hover { color: #475569; }

.filter-pills {
  display: flex;
  gap: 6px;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  border-radius: 999px;
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s ease;
}
.pill:hover { color: #0f172a; border-color: #cbd5e1; }
.pill.active {
  background: #0f172a;
  color: #ffffff;
  border-color: #0f172a;
}
.pill-count {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-weight: 600;
}
.pill.active .pill-count {
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
}

/* ---- Algorithm grid ---- */
.algo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.algo-card {
  background: #ffffff;
  border: 1px solid #eef2f6;
  border-radius: 14px;
  padding: 18px 20px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.algo-card:hover {
  border-color: #c7d2fe;
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.10);
  transform: translateY(-1px);
}
.algo-card.inactive {
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  opacity: 0.86;
}

.algo-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.algo-card-title { min-width: 0; }
.algo-code {
  display: inline-block;
  font-family: ui-monospace, SFMono-Regular, 'SF Mono', Consolas, 'Liberation Mono', monospace;
  font-size: 11.5px;
  font-weight: 600;
  background: #f1f5f9;
  color: #475569;
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.01em;
  margin-bottom: 6px;
}
.algo-card-title h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.3;
}

.algo-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.engine-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid;
}
.engine-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}
.engine-cloud_api { color: #4f46e5; background: #eef2ff; border-color: #e0e7ff; }
.engine-cloud_api .engine-dot { background: #6366f1; }
.engine-mock { color: #047857; background: #ecfdf5; border-color: #d1fae5; }
.engine-mock .engine-dot { background: #10b981; }
.engine-hikvision_brain { color: #b45309; background: #fffbeb; border-color: #fde68a; }
.engine-hikvision_brain .engine-dot { background: #f59e0b; }
.engine-multimodal_llm { color: #6d28d9; background: #f5f3ff; border-color: #ddd6fe; }
.engine-multimodal_llm .engine-dot { background: #8b5cf6; }
.engine-local_model { color: #0e7490; background: #ecfeff; border-color: #cffafe; }
.engine-local_model .engine-dot { background: #06b6d4; }

.category-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #64748b;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
  padding: 2px 8px;
  border-radius: 6px;
}
.category-pill .el-icon { font-size: 12px; }

.version-pill {
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: #94a3b8;
  margin-left: auto;
}

.algo-desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #334155;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.algo-desc.muted { color: #94a3b8; font-style: italic; }

.algo-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px dashed #eef2f6;
}
.algo-actions { display: flex; gap: 4px; }
.muted { color: #94a3b8; }
.small { font-size: 12px; }

/* ---- Empty ---- */
.empty {
  text-align: center;
  padding: 56px 20px;
  background: #ffffff;
  border: 1px dashed #e2e8f0;
  border-radius: 14px;
  color: #64748b;
}
.empty .el-icon.empty-icon {
  font-size: 38px;
  color: #cbd5e1;
  margin-bottom: 8px;
}
.empty h3 { margin: 0 0 4px; font-size: 15px; color: #0f172a; font-weight: 600; }
.empty p { margin: 0; font-size: 13px; }

/* ---- LLM tab ---- */
.llm-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.llm-card {
  background: #ffffff;
  border: 1px solid #eef2f6;
  border-radius: 14px;
  padding: 20px 22px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.llm-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.llm-card-header h2 {
  margin: 0 0 2px;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.llm-card-header p { margin: 0; }

.config-fields {
  display: flex;
  flex-direction: column;
  gap: 0;
  border-top: 1px solid #eef2f6;
}
.config-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #eef2f6;
}
.config-field:last-child { border-bottom: 0; }
.field-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
}
.field-label .el-icon { color: #94a3b8; font-size: 14px; }
.field-value {
  font-size: 13.5px;
  color: #0f172a;
  font-weight: 500;
  text-align: right;
  word-break: break-all;
}
.field-value.mono {
  font-family: ui-monospace, monospace;
  font-size: 12.5px;
  color: #475569;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid;
}
.status-tag.active { color: #047857; background: #ecfdf5; border-color: #d1fae5; }
.status-tag.inactive { color: #b45309; background: #fffbeb; border-color: #fde68a; }
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.status-tag.active .status-dot { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18); }
.status-tag.inactive .status-dot { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18); }

.test-area {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  background: linear-gradient(180deg, #f8fafc, #ffffff);
  border: 1px solid #eef2f6;
  border-radius: 12px;
}
.test-prompt {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 13px;
  color: #475569;
}
.test-prompt-label {
  display: inline-block;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #94a3b8;
}
.test-prompt code {
  font-family: ui-monospace, monospace;
  font-size: 12.5px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 2px 8px;
  color: #0f172a;
}

.test-result {
  border: 1px solid;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.test-result.success { border-color: #d1fae5; background: #f0fdf4; }
.test-result.fail { border-color: #fecaca; background: #fef2f2; }
.test-result-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.test-result-header strong {
  display: block;
  font-size: 14px;
  color: #0f172a;
}
.test-result-header p { margin: 2px 0 0; font-size: 12.5px; color: #475569; }
.result-icon { font-size: 22px; }
.test-result.success .result-icon { color: #10b981; }
.test-result.fail .result-icon { color: #f43f5e; }

.result-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 8px;
  font-size: 12.5px;
}
.result-meta > div { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.result-meta dt { color: #64748b; font-weight: 500; }
.result-meta dd { margin: 0; color: #0f172a; font-weight: 600; }
.token-pill {
  display: inline-block;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #475569;
  margin-right: 4px;
}
.token-pill.total { background: #eef2ff; color: #4f46e5; font-weight: 600; }
.result-preview {
  margin: 0;
  padding: 10px 12px;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  font-family: ui-monospace, monospace;
  font-size: 12.5px;
  line-height: 1.5;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---- Banner ---- */
.banner {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid;
  margin-bottom: 16px;
}
.banner .el-icon { font-size: 18px; margin-top: 1px; }
.banner strong { display: block; font-size: 13.5px; color: #0f172a; margin-bottom: 2px; }
.banner p { margin: 0; font-size: 12.5px; line-height: 1.5; }
.banner-warning { background: #fffbeb; border-color: #fde68a; }
.banner-warning .el-icon { color: #f59e0b; }
.banner-info { background: #f0f9ff; border-color: #bae6fd; }
.banner-info .el-icon { color: #0284c7; }

/* ---- Dialogs ---- */
.settings-dialog :deep(.el-dialog__header) {
  padding: 18px 24px;
  margin: 0;
  border-bottom: 1px solid #eef2f6;
}
.settings-dialog :deep(.el-dialog__title) {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}
.settings-dialog :deep(.el-dialog__body) { padding: 20px 24px; }
.settings-dialog :deep(.el-dialog__footer) {
  padding: 14px 24px;
  border-top: 1px solid #eef2f6;
  margin: 0;
}
.create-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #475569;
}
.form-hint {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}

/* ---- 动态引擎配置表单 ---- */
.config-form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #eef2f6;
}
.config-fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.config-field-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.config-field-label {
  flex: 0 0 130px;
  font-size: 13px;
  font-weight: 500;
  color: #475569;
  padding-top: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.config-field-control {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.config-field-control :deep(.el-input__wrapper) {
  background: #f8fafc;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  border-radius: 9px;
}
.config-field-control :deep(.el-input__wrapper):hover { box-shadow: 0 0 0 1px #cbd5e1 inset; }
.config-field-control :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px #6366f1 inset, 0 0 0 3px rgba(99, 102, 241, 0.1); }
.sensitive-tag {
  font-size: 10px;
  font-weight: 600;
  color: #b45309;
  background: #fffbeb;
  padding: 1px 6px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.slider-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}
.slider-wrap :deep(.el-slider) { flex: 1; margin-right: 0; }
.slider-wrap :deep(.el-slider__input) { width: 80px !important; }
.slider-value {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  color: #475569;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 5px;
  min-width: 36px;
  text-align: center;
}
.json-input :deep(textarea) {
  font-family: ui-monospace, monospace;
  font-size: 12.5px;
  background: #f8fafc;
}
.info-table :deep(.el-descriptions__label) {
  color: #64748b;
  font-weight: 500;
  background: #f8fafc;
}
.info-table :deep(.el-descriptions__content) {
  color: #0f172a;
}
.json-title {
  margin: 20px 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
}
.json-block {
  margin: 0;
  padding: 12px 14px;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 10px;
  font-family: ui-monospace, monospace;
  font-size: 12.5px;
  line-height: 1.6;
  overflow: auto;
  white-space: pre;
  max-height: 280px;
}

/* ---- Element Plus overrides ---- */
.algo-card :deep(.el-switch__core) {
  border-color: #cbd5e1;
}
.settings-page :deep(.el-button--primary) {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  border-color: #4f46e5;
  box-shadow: 0 1px 2px rgba(79, 70, 229, 0.18);
}
.settings-page :deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #4f46e5, #4338ca);
  border-color: #4338ca;
}

/* ---- Responsive ---- */
@media (max-width: 960px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .llm-grid { grid-template-columns: 1fr; }
  .hero { flex-direction: column; align-items: flex-start; }
  .hero-actions { width: 100%; }
}
@media (max-width: 640px) {
  .stats { grid-template-columns: 1fr; }
  .algo-grid { grid-template-columns: 1fr; }
  .toolbar { flex-direction: column; align-items: stretch; }
  .search-box { min-width: 0; }
  .filter-pills { overflow-x: auto; }
}
</style>
