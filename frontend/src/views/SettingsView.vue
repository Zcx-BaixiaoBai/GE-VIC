<template>
  <div>
    <h2>系统设置</h2>
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 算法配置 -->
      <el-tab-pane label="算法配置" name="algorithms">
        <div style="margin-bottom: 12px; display: flex; gap: 12px;">
          <el-button type="primary" @click="openCreateDialog">+ 新增算法</el-button>
          <el-button @click="loadAlgorithms">刷新</el-button>
          <span style="color: #909399; line-height: 32px; font-size: 13px;">
            共 {{ algorithms.length }} 个算法 ({{ activeCount }} 启用)
          </span>
        </div>

        <el-table :data="algorithms" v-loading="loading" stripe>
          <el-table-column prop="code" label="Code" width="200" />
          <el-table-column prop="name" label="名称" min-width="180" />
          <el-table-column prop="category" label="类别" width="120" />
          <el-table-column label="引擎" width="120">
            <template #default="{ row }">
              <el-tag :type="engineTypeColor(row.engine_type)" size="small">
                {{ engineTypeLabel(row.engine_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="100">
            <template #default="{ row }">
              <el-switch
                v-model="row.is_active"
                @change="(v: boolean | string | number) => onToggleActive(row, Boolean(v))"
                :loading="row._toggling"
              />
            </template>
          </el-table-column>
          <el-table-column prop="version" label="版本" width="60" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="showConfig(row)">查看配置</el-button>
              <el-button size="small" type="danger" @click="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 新增算法对话框 -->
        <el-dialog v-model="createDialogVisible" title="新增算法" width="600px">
          <el-form :model="createForm" label-width="100px" :rules="createRules" ref="createFormRef">
            <el-form-item label="Code" prop="code">
              <el-input v-model="createForm.code" placeholder="小写字母+数字+连字符" />
            </el-form-item>
            <el-form-item label="名称" prop="name">
              <el-input v-model="createForm.name" placeholder="显示名称" />
            </el-form-item>
            <el-form-item label="类别">
              <el-input v-model="createForm.category" placeholder="如: 供配电 / 供水 / 排水" />
            </el-form-item>
            <el-form-item label="引擎类型" prop="engine_type">
              <el-select v-model="createForm.engine_type" style="width: 100%">
                <el-option label="Mock 引擎 (本地测试)" value="mock" />
                <el-option label="Cloud API (阿里云/腾讯云等)" value="cloud_api" />
                <el-option label="海康超脑" value="hikvision_brain" />
                <el-option label="本地模型" value="local_model" />
              </el-select>
            </el-form-item>
            <el-form-item label="引擎配置 (JSON)">
              <el-input
                v-model="createForm.engineConfigStr"
                type="textarea"
                :rows="5"
                placeholder='{"delay_ms": 500, "defects_count": 1}'
              />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="createDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="creating" @click="onCreate">创建</el-button>
          </template>
        </el-dialog>

        <!-- 配置详情对话框 -->
        <el-dialog v-model="configDialogVisible" :title="`算法配置: ${selectedAlgo?.code || ''}`" width="700px">
          <div v-if="selectedAlgo" v-loading="configLoading">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="Code">{{ selectedAlgo.code }}</el-descriptions-item>
              <el-descriptions-item label="名称">{{ selectedAlgo.name }}</el-descriptions-item>
              <el-descriptions-item label="类别">{{ selectedAlgo.category || '-' }}</el-descriptions-item>
              <el-descriptions-item label="引擎类型">
                <el-tag :type="engineTypeColor(selectedAlgo.engine_type)" size="small">
                  {{ engineTypeLabel(selectedAlgo.engine_type) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="启用状态">
                <el-tag :type="selectedAlgo.is_active ? 'success' : 'info'" size="small">
                  {{ selectedAlgo.is_active ? '已启用' : '已停用' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="版本">{{ selectedAlgo.version }}</el-descriptions-item>
              <el-descriptions-item label="描述">{{ selectedAlgo.description || '-' }}</el-descriptions-item>
            </el-descriptions>
            <h4 style="margin-top: 16px;">引擎配置 (engine_config):</h4>
            <pre style="background: #f5f7fa; padding: 12px; border-radius: 4px; overflow: auto;">{{ formatJson(selectedAlgo.engine_config) }}</pre>
            <h4 style="margin-top: 16px;">请求 schema (request_schema):</h4>
            <pre style="background: #f5f7fa; padding: 12px; border-radius: 4px; overflow: auto;">{{ formatJson(selectedAlgo.request_schema) }}</pre>
          </div>
        </el-dialog>
      </el-tab-pane>

      <!-- LLM 模型配置 -->
      <el-tab-pane label="LLM 模型" name="llm">
        <el-card v-loading="llmLoading">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: 600;">LLM 富化服务配置</span>
              <el-button @click="loadLLM">刷新</el-button>
            </div>
          </template>

          <el-alert
            v-if="llmConfig?.mock_mode"
            type="warning"
            :closable="false"
            style="margin-bottom: 16px;"
          >
            <strong>当前为演示模式 (LLM_MOCK_MODE=true)</strong>: LLM 客户端返回预设响应, 不调用真实 API。
            生产部署需在环境变量中关闭此开关并配置真实凭据。
          </el-alert>

          <el-descriptions :column="2" border>
            <el-descriptions-item label="Base URL">{{ llmConfig?.base_url || '-' }}</el-descriptions-item>
            <el-descriptions-item label="Model">{{ llmConfig?.model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="Max Input Tokens">{{ llmConfig?.max_input_tokens || '-' }}</el-descriptions-item>
            <el-descriptions-item label="Max Output Tokens">{{ llmConfig?.max_output_tokens || '-' }}</el-descriptions-item>
            <el-descriptions-item label="Mock Mode" :span="2">
              <el-tag :type="llmConfig?.mock_mode ? 'warning' : 'success'" size="small">
                {{ llmConfig?.mock_mode ? '是 (演示模式)' : '否 (真实调用)' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <div style="margin-top: 20px;">
            <h4>连接测试</h4>
            <p style="color: #909399; font-size: 13px;">
              发送一个最小 prompt ("Reply with the single word: OK") 验证 LLM 服务可达。
            </p>
            <el-button type="primary" :loading="llmTesting" @click="onTestLLM">
              {{ llmTestResult ? '再次测试' : '运行测试' }}
            </el-button>

            <div v-if="llmTestResult" style="margin-top: 16px;">
              <el-alert
                :type="llmTestResult.success ? 'success' : 'error'"
                :title="llmTestResult.success ? '连接成功' : '连接失败'"
                :closable="false"
              >
                <div><strong>消息:</strong> {{ llmTestResult.message }}</div>
                <div v-if="llmTestResult.model"><strong>模型:</strong> {{ llmTestResult.model }}</div>
                <div v-if="llmTestResult.total_tokens">
                  <strong>Token 用量:</strong>
                  prompt={{ llmTestResult.prompt_tokens }}
                  completion={{ llmTestResult.completion_tokens }}
                  total={{ llmTestResult.total_tokens }}
                </div>
                <div v-if="llmTestResult.duration_ms">
                  <strong>耗时:</strong> {{ llmTestResult.duration_ms }}ms
                </div>
                <div v-if="llmTestResult.content_preview" style="margin-top: 8px;">
                  <strong>响应预览:</strong>
                  <pre style="background: #f5f7fa; padding: 8px; border-radius: 4px; margin-top: 4px; max-height: 200px; overflow: auto;">{{ llmTestResult.content_preview }}</pre>
                </div>
              </el-alert>
            </div>
          </div>

          <el-alert
            type="info"
            :closable="false"
            style="margin-top: 20px;"
          >
            <strong>配置方式</strong>: LLM 配置通过环境变量 (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / LLM_MOCK_MODE) 注入。
            修改配置需重启后端进程, 然后点击刷新查看新值。
          </el-alert>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { algorithmsApi, settingsApi, type Algorithm, type LLMConfig, type LLMTestResult } from '../api/client'

interface AlgorithmWithMeta extends Algorithm { _toggling?: boolean }

const activeTab = ref('algorithms')

// 算法管理
const algorithms = ref<AlgorithmWithMeta[]>([])
const loading = ref(false)
const activeCount = computed(() => algorithms.value.filter((a) => a.is_active).length)

const createDialogVisible = ref(false)
const creating = ref(false)
const createFormRef = ref()
const createForm = ref({
  code: '',
  name: '',
  category: '',
  engine_type: 'mock',
  engineConfigStr: '{}',
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

function engineTypeColor(t: string): string {
  const map: Record<string, string> = {
    cloud_api: 'primary',
    mock: 'success',
    hikvision_brain: 'warning',
    local_model: 'info',
  }
  return map[t] || 'info'
}

function engineTypeLabel(t: string): string {
  const map: Record<string, string> = {
    cloud_api: '云 API',
    mock: 'Mock',
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
  } catch (e) {
    row.is_active = !val // revert
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

function openCreateDialog() {
  createForm.value = {
    code: '',
    name: '',
    category: '',
    engine_type: 'mock',
    engineConfigStr: '{"delay_ms": 500}',
  }
  createDialogVisible.value = true
}

async function onCreate() {
  if (!createFormRef.value) return
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return

  let engineConfig: any = {}
  if (createForm.value.engineConfigStr.trim()) {
    try {
      engineConfig = JSON.parse(createForm.value.engineConfigStr)
    } catch (e) {
      ElMessage.error('引擎配置 JSON 解析失败: ' + e)
      return
    }
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

onMounted(() => {
  loadAlgorithms()
  loadLLM()
})
</script>
