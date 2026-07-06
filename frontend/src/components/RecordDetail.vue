<template>
  <el-drawer v-model="visible" :title="`记录 #${record?.id}`" size="65%">
    <div v-if="record" v-loading="loading">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ record.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="record.status" :enrichment-status="record.enrichment_status" />
        </el-descriptions-item>
        <el-descriptions-item label="算法">
          <div class="algo-cell-group">
            <code class="algo-cell">{{ record.algorithm_code }}</code>
            <EngineBadge :type="engineTypeOf(record.algorithm_code)" />
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="类别">{{ record.category || '-' }}</el-descriptions-item>
        <el-descriptions-item label="巡检员">{{ record.inspector_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="资产">{{ record.asset_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ formatTime(record.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatTime(record.finished_at) }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ record.duration_ms ? `${record.duration_ms}ms` : '-' }}</el-descriptions-item>
        <el-descriptions-item label="重试次数">{{ record.retry_count }}</el-descriptions-item>
      </el-descriptions>

      <el-divider>原文件</el-divider>
      <div v-if="record.file">
        <el-image
          v-if="record.file.type === 'image'"
          :src="record.file.url"
          :preview-src-list="[record.file.url]"
          fit="contain"
          style="max-width: 100%; max-height: 400px;"
        />
        <el-link v-else :href="record.file.url" target="_blank" type="primary">
          下载 {{ record.file.type }} 文件 ({{ record.file.size }} bytes)
        </el-link>
      </div>
      <el-empty v-else description="无文件" />

      <el-divider>识别结果</el-divider>
      <div v-if="record.summary">
        <p class="summary-line"><strong>一句话总结:</strong> {{ record.summary }}</p>
      </div>

      <!-- 多模态 LLM 结果 (有 observations) -->
      <div v-if="isMultimodalResult && record.recognition" class="multimodal-result">
        <div class="mm-header">
          <span :class="['media-badge', 'media-' + (record.recognition.media_type || 'unknown')]">
            {{ mediaLabel(record.recognition.media_type) }}
          </span>
          <el-tag v-if="record.recognition._format" size="small" effect="plain">
            解析: {{ record.recognition._format }}
          </el-tag>
        </div>

        <!-- 安全警示 -->
        <el-alert
          v-if="record.recognition.warnings?.length"
          :title="`安全警示 (${record.recognition.warnings.length})`"
          type="warning"
          :closable="false"
          style="margin-bottom: 12px;"
        >
          <ul class="warn-list">
            <li v-for="(w, i) in record.recognition.warnings" :key="i">{{ w }}</li>
          </ul>
        </el-alert>

        <p v-if="record.recognition.description" class="mm-description">
          {{ record.recognition.description }}
        </p>

        <h4 class="mm-section-title">观察 ({{ record.recognition.observations?.length || 0 }})</h4>
        <ul class="mm-observations">
          <li v-for="(obs, i) in record.recognition.observations" :key="i" class="mm-obs">
            <div class="mm-obs-head">
              <span v-if="obs.risk" :class="['mm-obs-risk', 'risk-' + riskClass(obs.risk)]" :title="`风险: ${obs.risk}`">
                {{ obs.risk }}
              </span>
              <span v-if="obs.type" class="mm-obs-type">{{ obs.type }}</span>
              <span class="mm-obs-label">{{ obs.label }}</span>
              <span v-if="obs.confidence != null" class="mm-obs-conf">
                {{ Math.round((Number(obs.confidence) || 0) * 100) }}%
              </span>
            </div>
            <div v-if="obs.brand || obs.status" class="mm-obs-meta">
              <span v-if="obs.brand"><strong>品牌:</strong> {{ obs.brand }}</span>
              <span v-if="obs.status"><strong>状态:</strong> {{ obs.status }}</span>
            </div>
            <p v-if="obs.note" class="mm-obs-note">{{ obs.note }}</p>
            <table v-if="obs.parameters?.length" class="mm-param-table">
              <thead>
                <tr><th>参数</th><th>读数</th><th>单位</th><th>偏离</th></tr>
              </thead>
              <tbody>
                <tr v-for="(p, j) in obs.parameters" :key="j">
                  <td>{{ p.key }}</td>
                  <td>{{ p.value }}</td>
                  <td>{{ p.unit || '' }}</td>
                  <td :class="deviationClass(p.deviation)">{{ p.deviation || '' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="obs.recommendation || obs.recommendation_detail" class="mm-obs-rec">
              <el-tag v-if="obs.recommendation" :type="priorityType(obs.recommendation)" size="small">
                {{ obs.recommendation }}
              </el-tag>
              <span v-if="obs.recommendation_detail" class="rec-detail">
                {{ obs.recommendation_detail }}
              </span>
            </div>
          </li>
        </ul>

        <details v-if="record.recognition._input || record.recognition._usage" class="mm-meta">
          <summary>详细信息</summary>
          <pre>{{ JSON.stringify({ _input: record.recognition._input, _usage: record.recognition._usage, _model: record.recognition._model }, null, 2) }}</pre>
        </details>

        <details v-if="record.recognition._raw_llm_content" class="mm-raw">
          <summary>LLM 原始输出</summary>
          <pre class="raw-block">{{ record.recognition._raw_llm_content }}</pre>
        </details>
      </div>

      <!-- 通用 JSON 视图 -->
      <pre v-else-if="record.recognition" class="json-block">{{ JSON.stringify(record.recognition, null, 2) }}</pre>
      <el-empty v-else description="无识别结果" />

      <el-divider>LLM 富化</el-divider>
      <div v-if="record.llm_enrichment?.summary">
        <h4>{{ record.llm_enrichment.summary }}</h4>
        <el-alert
          v-for="(rec, i) in record.llm_enrichment.recommendations || []"
          :key="i"
          :title="`建议 ${i + 1}`"
          :description="rec"
          type="info"
          :closable="false"
          style="margin-bottom: 8px"
        />
        <p style="color: #909399; font-size: 12px; margin-top: 12px;">
          模型: {{ record.llm_enrichment.model }} · token: {{ record.llm_enrichment.token_used }}
        </p>
        <details v-if="record.llm_enrichment.raw_content" class="mm-raw">
          <summary>富化原始输出</summary>
          <pre class="raw-block">{{ record.llm_enrichment.raw_content }}</pre>
        </details>
      </div>
      <el-empty v-else description="富化未生成" />

      <div v-if="record.status === 'SUCCESS'" style="margin-top: 16px;">
        <el-button
          v-if="!record.llm_enrichment || record.enrichment_status === 'ENRICH_FAILED'"
          type="primary"
          size="small"
          :loading="enriching"
          @click="onEnrich"
        >
          {{ record.llm_enrichment ? '重新富化' : '生成富化' }}
        </el-button>
      </div>

      <el-alert
        v-if="record.error"
        :title="record.error.code || '错误'"
        :description="record.error.message"
        type="error"
        :closable="false"
        style="margin-top: 16px"
      />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import EngineBadge from './EngineBadge.vue'
import { useRecordsStore } from '../stores/records'
import StatusTag from './StatusTag.vue'
import { recordsApi, type Inspection } from '../api/client'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  record: Inspection | null
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'refresh'): void
}>()

const visible = ref(props.modelValue)
const loading = ref(false)
const enriching = ref(false)

watch(() => props.modelValue, (v) => (visible.value = v))
watch(visible, (v) => emit('update:modelValue', v))

const isMultimodalResult = computed(() => {
  const r: any = props.record?.recognition
  return r && Array.isArray(r.observations) && (r.media_type === 'image' || r.media_type === 'video' || r.media_type === 'batch')
})

const store = useRecordsStore()
function engineTypeOf(code: string): string {
  const a = store.algorithms.find((x) => x.code === code)
  return a ? a.engine_type : ''
}
function mediaLabel(t: string): string {
  const m: Record<string, string> = { image: '图片', video: '视频', batch: '批量', unknown: '未知' }
  return m[t] || t
}

function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

function riskClass(r: string): string {
  if (!r) return 'unknown'
  if (r.includes('🔴') || r.includes('故障') || r.includes('严重')) return 'high'
  if (r.includes('🟡') || r.includes('预警') || r.includes('偏差') || r.includes('较差')) return 'medium'
  if (r.includes('🟢') || r.includes('正常') || r.includes('✅')) return 'low'
  return 'unknown'
}

function priorityType(p: string): 'success' | 'warning' | 'danger' | 'info' {
  if (!p) return 'info'
  if (p.includes('P0')) return 'danger'
  if (p.includes('P1')) return 'warning'
  if (p.includes('P2') || p.includes('P3')) return 'info'
  return 'info'
}

function deviationClass(d: string): string {
  if (!d) return ''
  if (d.includes('🔴') || d.includes('严重') || d.includes('故障') || d.includes('异常')) return 'dev-high'
  if (d.includes('🟡') || d.includes('⚠') || d.includes('偏高') || d.includes('偏低')) return 'dev-medium'
  if (d.includes('🟢') || d.includes('正常')) return 'dev-low'
  return ''
}

async function onEnrich() {
  if (!props.record) return
  enriching.value = true
  try {
    await recordsApi.enrich(props.record.id)
    ElMessage.success('富化任务已提交, 稍后刷新查看结果')
    emit('refresh')
  } finally {
    enriching.value = false
  }
}
</script>

<style scoped>
.mm-header { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.media-badge {
  display: inline-block; padding: 2px 10px; border-radius: 12px;
  font-size: 12px; font-weight: 500;
}
.media-image { background: #e1f3d8; color: #67c23a; }
.media-video { background: #fde2e2; color: #f56c6c; }
.media-batch { background: #ecf5ff; color: #409eff; }
.media-unknown { background: #f4f4f5; color: #909399; }

.mm-description { color: #606266; font-size: 13px; margin: 6px 0 12px; }
.mm-section-title { font-size: 14px; font-weight: 600; color: #303133; margin: 16px 0 8px; }

.mm-observations { list-style: none; padding: 0; margin: 0; }
.mm-obs {
  border: 1px solid #ebeef5; border-radius: 8px;
  padding: 12px; margin-bottom: 12px; background: #fafbfc;
}
.mm-obs-head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.mm-obs-type { font-size: 12px; color: #909399; }
.mm-obs-label { font-weight: 500; color: #303133; }
.mm-obs-conf { font-size: 12px; color: #67c23a; margin-left: auto; }
.mm-obs-risk {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 50%;
  font-size: 16px; flex-shrink: 0;
}
.risk-high { background: #fef0f0; color: #f56c6c; }
.risk-medium { background: #fdf6ec; color: #e6a23c; }
.risk-low { background: #f0f9eb; color: #67c23a; }
.risk-unknown { background: #f4f4f5; color: #909399; }

.mm-obs-meta {
  display: flex; gap: 16px; font-size: 12px; color: #606266;
  margin: 6px 0;
}
.mm-obs-note { font-size: 13px; color: #303133; line-height: 1.6; margin: 4px 0 8px; }

.mm-param-table {
  width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px;
}
.mm-param-table th, .mm-param-table td {
  padding: 6px 10px; border: 1px solid #ebeef5; text-align: left;
}
.mm-param-table th { background: #f5f7fa; font-weight: 500; }
.dev-high { color: #f56c6c; font-weight: 500; }
.dev-medium { color: #e6a23c; }
.dev-low { color: #67c23a; }

.mm-obs-rec { display: flex; gap: 8px; align-items: flex-start; margin-top: 8px; }
.rec-detail { font-size: 12px; color: #606266; line-height: 1.5; }

.warn-list { margin: 0; padding-left: 20px; font-size: 13px; line-height: 1.8; }
.summary-line { font-size: 14px; color: #303133; }
.json-block { background: #f5f7fa; padding: 12px; border-radius: 4px; font-size: 12px; overflow: auto; }
.mm-meta, .mm-raw { margin-top: 12px; }
.mm-meta summary, .mm-raw summary { cursor: pointer; color: #409eff; font-size: 12px; }
.raw-block { background: #fafafa; padding: 12px; border-radius: 4px; font-size: 11px; max-height: 400px; overflow: auto; white-space: pre-wrap; }
</style>
