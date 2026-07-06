<template>
  <el-drawer v-model="visible" :title="`识别记录 #${record?.id}`" size="78%" :destroy-on-close="false">
    <div v-if="record" v-loading="loading" class="rd-root">
      <!-- ========== 顶部摘要卡片 ========== -->
      <el-card shadow="never" class="rd-header">
        <div class="rd-header-top">
          <div class="rd-header-left">
            <h2 class="rd-title">
              <span :class="['rd-risk-dot', 'risk-' + maxRiskClass]"></span>
              {{ displaySummary }}
            </h2>
            <div class="rd-meta">
              <el-tag size="small" effect="plain">
                <code>{{ record.algorithm_code }}</code>
              </el-tag>
              <el-tag size="small" :type="statusType" effect="plain">
                <StatusTag :status="record.status" :enrichment-status="record.enrichment_status" />
              </el-tag>
              <el-tag v-if="record.recognition?._format" size="small" effect="plain" type="info">
                解析: {{ record.recognition._format }}
              </el-tag>
              <el-tag v-if="record.recognition?.media_type" size="small" effect="plain">
                {{ mediaLabel(record.recognition.media_type) }}
                <span v-if="record.recognition?.batch_size" class="rd-batch">· {{ record.recognition.batch_size }} 张</span>
              </el-tag>
            </div>
          </div>
          <div class="rd-header-right">
            <div class="rd-stat">
              <div class="rd-stat-num">{{ record.recognition?.observations?.length || 0 }}</div>
              <div class="rd-stat-label">观察项</div>
            </div>
            <div class="rd-stat">
              <div class="rd-stat-num rd-stat-warn">{{ record.recognition?.warnings?.length || 0 }}</div>
              <div class="rd-stat-label">安全警示</div>
            </div>
            <div class="rd-stat">
              <div class="rd-stat-num rd-stat-danger">{{ riskCount('high') }}</div>
              <div class="rd-stat-label">高风险</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- ========== 描述/场景 ========== -->
      <div v-if="record.recognition?.description" class="rd-description">
        <el-icon><InfoFilled /></el-icon>
        <span>{{ record.recognition.description }}</span>
      </div>

      <!-- ========== 安全警示 ========== -->
      <el-alert
        v-if="record.recognition?.warnings?.length"
        class="rd-warn"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #title>
          <strong>安全警示 ({{ record.recognition.warnings.length }})</strong>
        </template>
        <ul class="rd-warn-list">
          <li v-for="(w, i) in record.recognition.warnings" :key="i">{{ w }}</li>
        </ul>
      </el-alert>

      <!-- ========== 设备观察 ========== -->
      <div v-if="isMultimodalResult" class="rd-section">
        <div class="rd-section-header">
          <h3>设备观察</h3>
          <span class="rd-section-hint">按风险等级排序</span>
        </div>
        <div class="rd-obs-list">
          <div
            v-for="(obs, i) in sortedObservations"
            :key="i"
            :class="['rd-obs', 'rd-obs-' + riskClass(obs.risk)]"
          >
            <!-- Header: 风险 + 设备名 + 优先级 -->
            <div class="rd-obs-header">
              <div class="rd-obs-risk-badge">
                <span :class="['rd-risk-circle', 'risk-' + riskClass(obs.risk)]">
                  {{ riskEmoji(obs.risk) }}
                </span>
                <div class="rd-risk-text">
                  <div class="rd-risk-label">{{ riskText(obs.risk) }}</div>
                  <div class="rd-risk-hint">{{ riskHint(obs.risk) }}</div>
                </div>
              </div>
              <div class="rd-obs-title">
                <h4>{{ obs.label }}</h4>
                <div class="rd-obs-tags">
                  <el-tag v-if="obs.type" size="small" effect="plain" type="info">{{ obs.type }}</el-tag>
                  <el-tag v-if="obs.confidence" size="small" effect="plain">
                    置信度: {{ formatConfidence(obs.confidence) }}
                  </el-tag>
                  <el-tag v-if="obs.recommendation" :type="priorityType(obs.recommendation)" size="small">
                    {{ obs.recommendation }}
                  </el-tag>
                </div>
              </div>
            </div>

            <!-- 元信息: 品牌 + 状态 -->
            <div v-if="obs.brand || obs.status" class="rd-obs-meta">
              <div v-if="obs.brand" class="rd-meta-item">
                <span class="rd-meta-key">品牌型号</span>
                <span class="rd-meta-val">{{ obs.brand }}</span>
              </div>
              <div v-if="obs.status" class="rd-meta-item">
                <span class="rd-meta-key">运行状态</span>
                <span class="rd-meta-val">{{ obs.status }}</span>
              </div>
            </div>

            <!-- 状态分析 -->
            <div v-if="obs.note" class="rd-obs-section">
              <div class="rd-section-label">
                <el-icon><Document /></el-icon>
                <span>状态分析</span>
              </div>
              <p class="rd-obs-note">{{ obs.note }}</p>
            </div>

            <!-- 参数读数表 -->
            <div v-if="obs.parameters?.length" class="rd-obs-section">
              <div class="rd-section-label">
                <el-icon><DataLine /></el-icon>
                <span>关键参数 ({{ obs.parameters.length }})</span>
              </div>
              <el-table :data="obs.parameters" size="small" :show-header="true" stripe class="rd-param-table" :max-height="320">
                <el-table-column prop="key" label="参数" min-width="160" />
                <el-table-column prop="value" label="读数" min-width="100">
                  <template #default="{ row }">
                    <strong>{{ row.value }}</strong>
                  </template>
                </el-table-column>
                <el-table-column prop="unit" label="单位" min-width="60" />
                <el-table-column prop="deviation" label="偏离" min-width="200">
                  <template #default="{ row }">
                    <span :class="['rd-dev', 'rd-dev-' + deviationClass(row.deviation)]">
                      {{ row.deviation || '—' }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- 巡检建议 -->
            <div v-if="obs.recommendation_detail" class="rd-obs-rec">
              <el-icon><Tools /></el-icon>
              <div class="rd-obs-rec-text">
                <strong>处置建议：</strong>
                <span>{{ obs.recommendation_detail }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ========== LLM 富化 ========== -->
      <div v-if="record.llm_enrichment?.summary" class="rd-section">
        <div class="rd-section-header">
          <h3>
            <el-icon><MagicStick /></el-icon>
            LLM 智能研判
          </h3>
          <span class="rd-section-hint">
            模型 {{ record.llm_enrichment.model }} · token {{ record.llm_enrichment.token_used }}
          </span>
        </div>
        <el-card shadow="never" class="rd-enrichment">
          <p class="rd-enrichment-summary">{{ record.llm_enrichment.summary }}</p>
          <div v-if="record.llm_enrichment.recommendations?.length" class="rd-enrichment-recs">
            <div
              v-for="(rec, i) in record.llm_enrichment.recommendations"
              :key="i"
              class="rd-enrichment-rec"
            >
              <div class="rd-rec-num">{{ i + 1 }}</div>
              <div class="rd-rec-text">{{ rec }}</div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- ========== 调试信息 (默认折叠) ========== -->
      <div class="rd-debug">
        <details class="rd-debug-fold">
          <summary>
            <el-icon><Setting /></el-icon>
            <span>调试信息 (Token 用量 / 原始输出)</span>
            <span class="rd-debug-hint">点击展开</span>
          </summary>
          <div class="rd-debug-body">
            <div v-if="record.recognition?._model || record.recognition?._usage" class="rd-debug-card">
              <h5>识别调用</h5>
              <p><strong>模型:</strong> {{ record.recognition?._model || '-' }}</p>
              <p v-if="record.recognition?._usage">
                <strong>Tokens:</strong>
                prompt {{ record.recognition._usage.prompt_tokens || 0 }} ·
                completion {{ record.recognition._usage.completion_tokens || 0 }} ·
                total {{ record.recognition._usage.total_tokens || 0 }}
              </p>
              <p><strong>耗时:</strong> {{ record.duration_ms ? `${record.duration_ms}ms` : '-' }}</p>
            </div>
            <div v-if="record.llm_enrichment" class="rd-debug-card">
              <h5>富化调用</h5>
              <p><strong>模型:</strong> {{ record.llm_enrichment.model }}</p>
              <p><strong>Token:</strong> {{ record.llm_enrichment.token_used }}</p>
            </div>
            <details v-if="record.recognition?._raw_llm_content" class="rd-debug-raw">
              <summary>识别 LLM 原始输出</summary>
              <pre class="rd-raw-pre">{{ record.recognition._raw_llm_content }}</pre>
            </details>
            <details v-if="record.llm_enrichment?.raw_content" class="rd-debug-raw">
              <summary>富化 LLM 原始输出</summary>
              <pre class="rd-raw-pre">{{ record.llm_enrichment.raw_content }}</pre>
            </details>
          </div>
        </details>
      </div>

      <!-- ========== 错误信息 ========== -->
      <el-alert
        v-if="record.error"
        :title="record.error.code || '错误'"
        :description="record.error.message"
        type="error"
        :closable="false"
        style="margin-top: 16px"
      />

      <!-- ========== 底部操作 ========== -->
      <div v-if="record.status === 'SUCCESS'" class="rd-footer">
        <el-button
          v-if="!record.llm_enrichment || record.enrichment_status === 'ENRICH_FAILED'"
          type="primary"
          :loading="enriching"
          @click="onEnrich"
        >
          <el-icon><MagicStick /></el-icon>
          {{ record.llm_enrichment ? '重新富化' : '生成富化报告' }}
        </el-button>
        <el-tag v-else-if="record.enrichment_status === 'ENRICHED'" type="success" effect="plain">
          富化已完成
        </el-tag>
        <el-tag v-else-if="record.enrichment_status === 'ENRICHING'" type="warning" effect="plain">
          富化中...
        </el-tag>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRecordsStore } from '../stores/records'
import StatusTag from './StatusTag.vue'
import { recordsApi, type Inspection } from '../api/client'
import { ElMessage } from 'element-plus'
import {
  InfoFilled, Document, DataLine, Tools, MagicStick, Setting,
} from '@element-plus/icons-vue'

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

const displaySummary = computed(() => {
  // 优先用 recognition 里的解析后 summary, 否则回退到 record.summary, 否则显示空
  const r = props.record?.recognition
  if (r?.summary) {
    const s = r.summary.replace(/\n/g, ' ').trim()
    if (s.length > 0) return s
  }
  return props.record?.summary || '（无总结）'
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

const statusType = computed(() => {
  const s = props.record?.status
  if (s === 'SUCCESS') return 'success'
  if (s === 'FAILED' || s === 'DEAD') return 'danger'
  if (s === 'RUNNING') return 'warning'
  return 'info'
})

const maxRiskClass = computed(() => {
  const obs = props.record?.recognition?.observations || []
  for (const o of obs) {
    if (riskClass(o.risk) === 'high') return 'high'
  }
  for (const o of obs) {
    if (riskClass(o.risk) === 'medium') return 'medium'
  }
  return 'low'
})

const sortedObservations = computed(() => {
  const obs = [...(props.record?.recognition?.observations || [])]
  const order: Record<string, number> = { high: 0, medium: 1, low: 2, unknown: 3 }
  return obs.sort((a, b) => (order[riskClass(a.risk)] ?? 4) - (order[riskClass(b.risk)] ?? 4))
})

function riskCount(level: 'high' | 'medium' | 'low'): number {
  return (props.record?.recognition?.observations || []).filter((o: any) => riskClass(o.risk) === level).length
}

function riskClass(r: any): 'high' | 'medium' | 'low' | 'unknown' {
  if (!r) return 'unknown'
  const s = String(r)
  if (s.includes('🔴') || s.includes('故障') || s.includes('严重') || s.includes('P0')) return 'high'
  if (s.includes('🟡') || s.includes('预警') || s.includes('偏差') || s.includes('较差') || s.includes('P1')) return 'medium'
  if (s.includes('🟢') || s.includes('正常') || s.includes('✅') || s.includes('P2') || s.includes('P3')) return 'low'
  return 'unknown'
}
function riskEmoji(r: any): string {
  const c = riskClass(r)
  if (c === 'high') return '🔴'
  if (c === 'medium') return '🟡'
  if (c === 'low') return '🟢'
  return '⚪'
}
function riskText(r: any): string {
  const c = riskClass(r)
  if (c === 'high') return '高风险'
  if (c === 'medium') return '中风险'
  if (c === 'low') return '低风险'
  return '未知'
}
function riskHint(r: any): string {
  const c = riskClass(r)
  if (c === 'high') return '需要立即处置'
  if (c === 'medium') return '需要关注'
  if (c === 'low') return '运行正常'
  return ''
}

function priorityType(p: string): 'success' | 'warning' | 'danger' | 'info' {
  if (!p) return 'info'
  if (p.includes('P0')) return 'danger'
  if (p.includes('P1')) return 'warning'
  if (p.includes('P2')) return 'info'
  if (p.includes('P3')) return 'success'
  return 'info'
}

function deviationClass(d: string): 'high' | 'medium' | 'low' | 'normal' {
  if (!d) return 'normal'
  if (d.includes('🔴') || d.includes('严重') || d.includes('故障') || d.includes('异常') || d.includes('停机')) return 'high'
  if (d.includes('🟡') || d.includes('⚠') || d.includes('偏高') || d.includes('偏低') || d.includes('预警')) return 'medium'
  if (d.includes('🟢') || d.includes('正常') || d.includes('一致')) return 'low'
  return 'normal'
}

function formatConfidence(c: any): string {
  if (c == null) return ''
  if (typeof c === 'number') return `${Math.round(c * 100)}%`
  return String(c)
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
.rd-root { padding: 0 4px; }

/* 顶部摘要卡片 */
.rd-header { border: none; background: linear-gradient(135deg, #f5f7fa 0%, #e8eef5 100%); margin-bottom: 16px; }
.rd-header-top { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
.rd-header-left { flex: 1; min-width: 0; }
.rd-title { margin: 0 0 12px; font-size: 18px; font-weight: 600; color: #303133; display: flex; align-items: center; gap: 10px; }
.rd-risk-dot {
  display: inline-block; width: 14px; height: 14px; border-radius: 50%;
  flex-shrink: 0; box-shadow: 0 0 0 3px rgba(255,255,255,0.5);
}
.rd-risk-dot.risk-high { background: #f56c6c; box-shadow: 0 0 0 3px rgba(245,108,108,0.2); }
.rd-risk-dot.risk-medium { background: #e6a23c; box-shadow: 0 0 0 3px rgba(230,162,60,0.2); }
.rd-risk-dot.risk-low { background: #67c23a; box-shadow: 0 0 0 3px rgba(103,194,58,0.2); }
.rd-risk-dot.risk-unknown { background: #c0c4cc; }
.rd-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.rd-batch { margin-left: 4px; opacity: 0.7; }
.rd-header-right { display: flex; gap: 20px; flex-shrink: 0; }
.rd-stat { text-align: center; padding: 0 12px; border-left: 1px solid #dcdfe6; }
.rd-stat-num { font-size: 24px; font-weight: 600; color: #303133; line-height: 1.2; }
.rd-stat-warn { color: #e6a23c; }
.rd-stat-danger { color: #f56c6c; }
.rd-stat-label { font-size: 12px; color: #909399; margin-top: 4px; }

/* 描述 */
.rd-description {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 10px 14px; background: #f5f7fa; border-radius: 6px;
  color: #606266; font-size: 13px; line-height: 1.6; margin-bottom: 16px;
}
.rd-description .el-icon { color: #909399; margin-top: 2px; flex-shrink: 0; }

/* 警示 */
.rd-warn { margin-bottom: 16px; }
.rd-warn-list { margin: 8px 0 0; padding-left: 20px; line-height: 1.8; font-size: 13px; }

/* 区块 */
.rd-section { margin-bottom: 24px; }
.rd-section-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; }
.rd-section-header h3 { margin: 0; font-size: 15px; font-weight: 600; color: #303133; display: flex; align-items: center; gap: 6px; }
.rd-section-hint { font-size: 12px; color: #909399; }

/* 观察卡片 */
.rd-obs-list { display: flex; flex-direction: column; gap: 12px; }
.rd-obs {
  background: #fff; border: 1px solid #ebeef5; border-radius: 10px;
  padding: 16px 18px; transition: all 0.2s; position: relative;
  border-left: 4px solid #c0c4cc;
}
.rd-obs:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
.rd-obs.rd-obs-high { border-left-color: #f56c6c; background: linear-gradient(90deg, #fef5f5 0%, #fff 30%); }
.rd-obs.rd-obs-medium { border-left-color: #e6a23c; background: linear-gradient(90deg, #fdf6ec 0%, #fff 30%); }
.rd-obs.rd-obs-low { border-left-color: #67c23a; background: linear-gradient(90deg, #f0f9eb 0%, #fff 30%); }

.rd-obs-header { display: flex; gap: 16px; align-items: flex-start; margin-bottom: 12px; }
.rd-obs-risk-badge { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.rd-risk-circle {
  width: 38px; height: 38px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
}
.rd-risk-circle.risk-high { background: #fef0f0; box-shadow: 0 2px 6px rgba(245,108,108,0.3); }
.rd-risk-circle.risk-medium { background: #fdf6ec; box-shadow: 0 2px 6px rgba(230,162,60,0.3); }
.rd-risk-circle.risk-low { background: #f0f9eb; box-shadow: 0 2px 6px rgba(103,194,58,0.3); }
.rd-risk-circle.risk-unknown { background: #f4f4f5; }
.rd-risk-text { display: flex; flex-direction: column; }
.rd-risk-label { font-size: 13px; font-weight: 600; color: #303133; }
.rd-risk-hint { font-size: 11px; color: #909399; }
.rd-obs-title { flex: 1; min-width: 0; }
.rd-obs-title h4 { margin: 0 0 6px; font-size: 15px; font-weight: 600; color: #303133; line-height: 1.4; }
.rd-obs-tags { display: flex; gap: 6px; flex-wrap: wrap; }

/* 元信息 */
.rd-obs-meta {
  display: flex; gap: 24px; flex-wrap: wrap;
  background: rgba(245,247,250,0.6); border-radius: 6px;
  padding: 10px 14px; margin-bottom: 12px;
}
.rd-meta-item { display: flex; flex-direction: column; gap: 2px; min-width: 120px; }
.rd-meta-key { font-size: 11px; color: #909399; }
.rd-meta-val { font-size: 13px; color: #303133; }

/* 子区块 */
.rd-obs-section { margin-bottom: 12px; }
.rd-section-label {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; font-weight: 500; color: #606266;
  margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px dashed #ebeef5;
}
.rd-section-label .el-icon { font-size: 12px; }
.rd-obs-note { margin: 0; font-size: 13px; color: #303133; line-height: 1.7; padding: 0 4px; }

/* 参数表 */
.rd-param-table { border-radius: 6px; overflow: hidden; }
.rd-dev { font-weight: 500; }
.rd-dev-high { color: #f56c6c; }
.rd-dev-medium { color: #e6a23c; }
.rd-dev-low { color: #67c23a; }
.rd-dev-normal { color: #909399; }

/* 建议 */
.rd-obs-rec {
  display: flex; gap: 8px; align-items: flex-start;
  background: #f0f8ff; border-left: 3px solid #409eff;
  padding: 10px 14px; border-radius: 4px; margin-top: 12px;
  font-size: 13px; line-height: 1.6;
}
.rd-obs-rec .el-icon { color: #409eff; margin-top: 2px; flex-shrink: 0; }
.rd-obs-rec-text { color: #303133; }
.rd-obs-rec-text strong { color: #409eff; }

/* 富化 */
.rd-enrichment { background: linear-gradient(135deg, #f0f8ff 0%, #f5f0ff 100%); border: none; }
.rd-enrichment-summary {
  font-size: 14px; color: #303133; line-height: 1.7; margin: 0 0 12px;
  padding: 12px 14px; background: rgba(255,255,255,0.6); border-radius: 6px;
}
.rd-enrichment-recs { display: flex; flex-direction: column; gap: 8px; }
.rd-enrichment-rec {
  display: flex; gap: 12px; align-items: flex-start;
  background: rgba(255,255,255,0.7); padding: 10px 14px; border-radius: 6px;
}
.rd-rec-num {
  width: 24px; height: 24px; border-radius: 50%;
  background: #409eff; color: #fff; font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.rd-rec-text { font-size: 13px; color: #303133; line-height: 1.6; }

/* 调试信息 - 极简折叠 */
.rd-debug { margin-top: 24px; }
.rd-debug-fold {
  background: #fafbfc; border: 1px solid #ebeef5; border-radius: 6px;
  padding: 0; transition: all 0.2s;
}
.rd-debug-fold[open] { background: #fff; }
.rd-debug-fold > summary {
  list-style: none; cursor: pointer; padding: 10px 14px;
  display: flex; align-items: center; gap: 8px;
  color: #909399; font-size: 13px; user-select: none;
  border-radius: 6px;
}
.rd-debug-fold > summary::-webkit-details-marker { display: none; }
.rd-debug-fold > summary:hover { background: #f0f2f5; }
.rd-debug-fold > summary .el-icon { font-size: 14px; }
.rd-debug-hint { margin-left: auto; font-size: 11px; color: #c0c4cc; }
.rd-debug-body { padding: 4px 14px 14px; }
.rd-debug-card { background: #fafafa; padding: 10px 12px; border-radius: 4px; font-size: 12px; margin-bottom: 8px; }
.rd-debug-card h5 { margin: 0 0 6px; font-size: 11px; color: #909399; font-weight: 500; }
.rd-debug-card p { margin: 2px 0; color: #606266; line-height: 1.6; }
.rd-debug-raw { margin-top: 6px; }
.rd-debug-raw > summary {
  cursor: pointer; color: #909399; font-size: 12px; padding: 6px 0;
  list-style: none; user-select: none;
}
.rd-debug-raw > summary::-webkit-details-marker { display: none; }
.rd-debug-raw > summary:before { content: "▸ "; font-size: 10px; }
.rd-debug-raw[open] > summary:before { content: "▾ "; }
.rd-raw-pre {
  background: #fafafa; padding: 10px; border-radius: 4px;
  font-size: 11px; max-height: 320px; overflow: auto; white-space: pre-wrap;
  border: 1px solid #ebeef5; margin: 6px 0 0;
  font-family: ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
}

/* 底部 */
.rd-footer { margin-top: 16px; display: flex; gap: 8px; align-items: center; }
</style>
