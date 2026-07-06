<template>
  <div class="dashboard-page">
    <!-- Hero -->
    <header class="hero">
      <div class="hero-text">
        <h1>仪表盘</h1>
        <p>实时统计 · 状态分布 · 最近活动 · 窗口期: <strong>最近 {{ windowDays }} 天</strong></p>
      </div>
      <div class="hero-actions">
        <el-button :icon="RefreshIcon" @click="reload" :loading="statsLoading || loading">刷新</el-button>
        <el-button type="primary" :icon="UploadIcon" @click="goUpload">上传识别</el-button>
      </div>
    </header>

    <!-- Stats row -->
    <section class="stats">
      <article class="stat-card tint-indigo">
        <div class="stat-icon"><el-icon><Document /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ stats?.total ?? '—' }}</div>
          <div class="stat-label">总记录数</div>
          <div class="stat-sub">今日 +{{ stats?.today_count ?? 0 }}</div>
        </div>
      </article>
      <article class="stat-card tint-emerald">
        <div class="stat-icon"><el-icon><CircleCheck /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ formatPct(stats?.success_rate) }}</div>
          <div class="stat-label">成功率</div>
          <div class="stat-sub">{{ stats?.by_status.success ?? 0 }} 条成功</div>
        </div>
      </article>
      <article class="stat-card tint-cyan">
        <div class="stat-icon"><el-icon><Timer /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ formatMs(stats?.avg_duration_ms) }}</div>
          <div class="stat-label">平均耗时</div>
          <div class="stat-sub">P95 {{ formatMs(stats?.p95_duration_ms) }}</div>
        </div>
      </article>
      <article class="stat-card tint-violet">
        <div class="stat-icon"><el-icon><MagicStick /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ formatPct(stats?.enrichment_rate) }}</div>
          <div class="stat-label">富化覆盖</div>
          <div class="stat-sub">{{ stats?.by_enrichment.enriched ?? 0 }} 条已富化</div>
        </div>
      </article>
      <article class="stat-card tint-amber">
        <div class="stat-icon"><el-icon><Loading /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ (stats?.by_status.pending ?? 0) + (stats?.by_status.running ?? 0) }}</div>
          <div class="stat-label">进行中</div>
          <div class="stat-sub">{{ stats?.by_status.running ?? 0 }} 运行 / {{ stats?.by_status.pending ?? 0 }} 等待</div>
        </div>
      </article>
      <article class="stat-card tint-rose">
        <div class="stat-icon"><el-icon><CircleClose /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ stats?.failure_count ?? 0 }}</div>
          <div class="stat-label">失败记录</div>
          <div class="stat-sub">{{ stats?.by_status.dead ?? 0 }} 永久失败</div>
        </div>
      </article>
    </section>

    <!-- Charts row -->
    <section class="charts">
      <article class="chart-card">
        <header class="chart-header">
          <div>
            <h2>状态分布</h2>
            <p class="muted small">所有 {{ stats?.total ?? 0 }} 条记录的当前状态</p>
          </div>
        </header>
        <div v-if="stats && stats.total > 0" class="stacked-bar">
          <div
            v-for="seg in statusSegments"
            :key="seg.key"
            :class="['seg', `seg-${seg.key}`]"
            :style="{ width: seg.pct + '%' }"
            :title="`${seg.label}: ${seg.count}`"
          ></div>
        </div>
        <div v-else class="empty-chart">暂无记录</div>
        <ul class="legend">
          <li v-for="seg in statusSegments" :key="seg.key">
            <span :class="['legend-dot', `seg-${seg.key}`]"></span>
            <span class="legend-label">{{ seg.label }}</span>
            <span class="legend-value">{{ seg.count }}</span>
            <span class="legend-pct">{{ formatPct(seg.pct / 100) }}</span>
          </li>
        </ul>
      </article>

      <article class="chart-card">
        <header class="chart-header">
          <div>
            <h2>算法使用排行</h2>
            <p class="muted small">TOP {{ stats?.by_algorithm?.length ?? 0 }} 个算法 (按调用次数)</p>
          </div>
        </header>
        <ul v-if="stats?.by_algorithm?.length" class="algo-list">
          <li v-for="(a, i) in stats.by_algorithm" :key="a.code" class="algo-row">
            <div class="algo-rank">{{ i + 1 }}</div>
            <div class="algo-info">
              <div class="algo-name">
                <code class="algo-code">{{ a.code }}</code>
                <span v-if="a.name" class="algo-label">{{ a.name }}</span>
              </div>
              <div class="algo-bar">
                <div class="algo-bar-fill" :style="{ width: pctOf(a.count, maxAlgoCount) + '%' }"></div>
              </div>
            </div>
            <div class="algo-count">{{ a.count }}</div>
          </li>
        </ul>
        <div v-else class="empty-chart">暂无数据</div>
      </article>
    </section>

    <!-- Recent records -->
    <section class="records-section">
      <header class="section-header">
        <div>
          <h2>最近记录</h2>
          <p class="muted small">最新 {{ records.length }} 条 · 共 {{ total }} 条</p>
        </div>
        <div class="header-actions">
          <el-select v-model="statusFilter" placeholder="状态" clearable size="small" style="width: 130px;">
            <el-option label="等待中" value="PENDING" />
            <el-option label="识别中" value="RUNNING" />
            <el-option label="成功" value="SUCCESS" />
            <el-option label="失败" value="FAILED" />
            <el-option label="已停止" value="DEAD" />
          </el-select>
          <el-select v-model="algoFilter" placeholder="算法" clearable size="small" style="width: 200px;">
            <el-option
              v-for="a in algorithms"
              :key="a.code"
              :label="`${a.name} (${a.code})`"
              :value="a.code"
            />
          </el-select>
        </div>
      </header>

      <div class="records-card">
        <table class="records-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>状态</th>
              <th>算法</th>
              <th>资产</th>
              <th>巡检员</th>
              <th>耗时</th>
              <th>提交时间</th>
              <th class="th-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading && records.length === 0">
              <td colspan="8" class="td-empty">加载中…</td>
            </tr>
            <tr v-else-if="records.length === 0">
              <td colspan="8" class="td-empty">
                <el-icon class="empty-icon"><FolderDelete /></el-icon>
                <span>没有匹配的记录</span>
              </td>
            </tr>
            <tr v-for="r in records" :key="r.id" @click="onSelect(r)">
              <td><code class="id-cell">#{{ r.id }}</code></td>
              <td>
                <span :class="['status-pill', `status-${r.status}`]">
                  <span class="pill-dot"></span>
                  {{ statusLabel(r.status) }}
                  <span v-if="r.status === 'SUCCESS' && r.enrichment_status === 'ENRICHED'" class="enrich-tag">已富化</span>
                  <span v-else-if="r.status === 'SUCCESS' && r.enrichment_status === 'ENRICH_FAILED'" class="enrich-tag warn">富化失败</span>
                </span>
              </td>
              <td>
                <div class="algo-cell-group">
                  <code class="algo-cell">{{ r.algorithm_code }}</code>
                  <EngineBadge :type="engineTypeOf(r.algorithm_code)" />
                </div>
              </td>
              <td class="td-meta">{{ r.asset_id || r.request_meta?.asset_id || '—' }}</td>
              <td class="td-meta">{{ r.inspector_id || r.request_meta?.inspector_id || '—' }}</td>
              <td class="td-num">{{ r.duration_ms ? `${r.duration_ms}ms` : '—' }}</td>
              <td class="td-meta">{{ formatTime(r.created_at) }}</td>
              <td class="th-actions" @click.stop>
                <button class="row-action" @click="onSelect(r)" title="查看">
                  <el-icon><View /></el-icon>
                </button>
                <button
                  v-if="['FAILED', 'DEAD'].includes(r.status)"
                  class="row-action warn"
                  @click="onRetry(r)"
                  title="重试"
                >
                  <el-icon><RefreshRight /></el-icon>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <RecordDetail v-model="drawerVisible" :record="selectedRecord" @refresh="reload" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useRecordsStore } from '../stores/records'
import { recordsApi, type Inspection } from '../api/client'
import RecordDetail from '../components/RecordDetail.vue'
import EngineBadge from '../components/EngineBadge.vue'
import { ElMessage } from 'element-plus'
import {
  CircleCheck,
  CircleClose,
  Document,
  FolderDelete,
  Loading,
  MagicStick,
  Refresh,
  RefreshRight,
  Timer,
  Upload,
  View,
} from '@element-plus/icons-vue'

const RefreshIcon = Refresh
const UploadIcon = Upload

const store = useRecordsStore()
const router = useRouter()
const drawerVisible = ref(false)
const selectedRecord = ref<Inspection | null>(null)
const statusFilter = ref<string>('')
const algoFilter = ref<string>('')

const records = computed(() => store.records)
const total = computed(() => store.total)
const loading = computed(() => store.loading)
const stats = computed(() => store.stats)
const statsLoading = computed(() => store.statsLoading)
const algorithms = computed(() => store.algorithms)

function engineTypeOf(code: string): string {
  const a = algorithms.value.find((x) => x.code === code)
  return a ? a.engine_type : ''
}
const windowDays = computed(() => stats.value?.window_days ?? 30)

const maxAlgoCount = computed(() => {
  const list = stats.value?.by_algorithm || []
  return list.length ? list[0].count : 1
})

const statusSegments = computed(() => {
  if (!stats.value) return []
  const total = stats.value.total || 1
  const items: { key: string; label: string; count: number; pct: number }[] = [
    { key: 'success', label: '成功', count: stats.value.by_status.success, pct: 0 },
    { key: 'running', label: '识别中', count: stats.value.by_status.running, pct: 0 },
    { key: 'pending', label: '等待中', count: stats.value.by_status.pending, pct: 0 },
    { key: 'failed', label: '失败', count: stats.value.by_status.failed, pct: 0 },
    { key: 'dead', label: '已停止', count: stats.value.by_status.dead, pct: 0 },
  ]
  return items.map((it) => ({ ...it, pct: (it.count / total) * 100 }))
})

function formatPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return '—'
  return (v * 100).toFixed(digits) + '%'
}

function formatMs(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  if (v < 1000) return `${Math.round(v)}ms`
  return `${(v / 1000).toFixed(2)}s`
}

function pctOf(n: number, total: number): number {
  if (!total) return 0
  return Math.max(2, (n / total) * 100)
}

function statusLabel(s: string): string {
  const m: Record<string, string> = {
    PENDING: '等待中',
    RUNNING: '识别中',
    SUCCESS: '成功',
    FAILED: '失败',
    DEAD: '已停止',
  }
  return m[s] || s
}

function formatTime(t: string | null | undefined): string {
  if (!t) return '—'
  const d = new Date(t)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function reload() {
  await Promise.all([store.fetchStats(), store.fetchRecords(filtersPayload())])
}

function filtersPayload() {
  const p: Record<string, any> = { limit: 50 }
  if (statusFilter.value) p.status = statusFilter.value
  if (algoFilter.value) p.algorithm = algoFilter.value
  return p
}

watch([statusFilter, algoFilter], () => {
  store.fetchRecords(filtersPayload())
})

onMounted(async () => {
  if (algorithms.value.length === 0) await store.fetchAlgorithms()
  await reload()
})

async function onSelect(r: Inspection) {
  selectedRecord.value = await store.fetchRecord(r.id)
  drawerVisible.value = true
}

async function onRetry(r: Inspection) {
  await recordsApi.retry(r.id)
  ElMessage.success(`记录 #${r.id} 重试已提交`)
  await reload()
}

function goUpload() {
  router.push('/upload')
}
</script>

<style scoped>
.dashboard-page {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  color: #0f172a;
  max-width: 1280px;
  margin: 0 auto;
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
}
.hero-text p {
  margin: 0;
  font-size: 13.5px;
  color: #64748b;
}
.hero-text strong { color: #0f172a; font-weight: 600; }
.hero-actions { display: flex; gap: 8px; }

/* ---- Stats (6 cards) ---- */
.stats {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}
.stat-card {
  background: #ffffff;
  border: 1px solid #eef2f6;
  border-radius: 14px;
  padding: 16px 18px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  min-width: 0;
}
.stat-card:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(15, 23, 42, 0.07); }
.stat-icon {
  width: 40px; height: 40px;
  border-radius: 11px;
  display: grid; place-items: center;
  font-size: 20px;
  flex-shrink: 0;
}
.stat-body { min-width: 0; flex: 1; }
.stat-value {
  font-size: 22px;
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
.stat-sub {
  margin-top: 4px;
  font-size: 11.5px;
  color: #94a3b8;
}
.tint-indigo .stat-icon { background: #eef2ff; color: #6366f1; }
.tint-emerald .stat-icon { background: #ecfdf5; color: #10b981; }
.tint-cyan .stat-icon { background: #ecfeff; color: #06b6d4; }
.tint-amber .stat-icon { background: #fffbeb; color: #f59e0b; }
.tint-rose .stat-icon { background: #fef2f2; color: #f43f5e; }
.tint-violet .stat-icon { background: #f5f3ff; color: #8b5cf6; }

/* ---- Charts ---- */
.charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
.chart-card {
  background: #ffffff;
  border: 1px solid #eef2f6;
  border-radius: 14px;
  padding: 20px 22px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.chart-header { margin-bottom: 16px; }
.chart-header h2 {
  margin: 0 0 2px;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.chart-header p { margin: 0; }

/* Stacked bar */
.stacked-bar {
  display: flex;
  height: 14px;
  border-radius: 999px;
  overflow: hidden;
  background: #f1f5f9;
  margin-bottom: 14px;
}
.seg { height: 100%; transition: width 0.3s ease; }
.seg-success { background: linear-gradient(90deg, #10b981, #34d399); }
.seg-running { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.seg-pending { background: linear-gradient(90deg, #94a3b8, #cbd5e1); }
.seg-failed { background: linear-gradient(90deg, #f43f5e, #fb7185); }
.seg-dead { background: linear-gradient(90deg, #be123c, #e11d48); }
.legend { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.legend li {
  display: grid;
  grid-template-columns: 12px 1fr auto auto;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
.legend-label { color: #334155; }
.legend-value { color: #0f172a; font-weight: 600; font-family: ui-monospace, monospace; font-size: 12.5px; }
.legend-pct { color: #94a3b8; font-size: 12px; min-width: 48px; text-align: right; }

.empty-chart {
  padding: 32px 0;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}

/* Algo list */
.algo-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.algo-row { display: grid; grid-template-columns: 22px 1fr auto; align-items: center; gap: 12px; }
.algo-rank {
  width: 22px; height: 22px;
  display: grid; place-items: center;
  background: #f1f5f9; color: #64748b;
  border-radius: 6px;
  font-size: 11.5px; font-weight: 700;
  font-family: ui-monospace, monospace;
}
.algo-info { min-width: 0; }
.algo-name { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.algo-code {
  font-family: ui-monospace, monospace;
  font-size: 11.5px;
  font-weight: 600;
  background: #f1f5f9;
  color: #475569;
  padding: 1px 6px;
  border-radius: 5px;
}
.algo-label { font-size: 12.5px; color: #64748b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.algo-bar { height: 6px; background: #f1f5f9; border-radius: 999px; overflow: hidden; }
.algo-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  border-radius: 999px;
  transition: width 0.4s ease;
}
.algo-count {
  font-family: ui-monospace, monospace;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  min-width: 36px;
  text-align: right;
}

/* ---- Records section ---- */
.records-section { display: flex; flex-direction: column; gap: 12px; }
.section-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.section-header h2 {
  margin: 0 0 2px;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
}
.section-header p { margin: 0; }
.header-actions { display: flex; gap: 8px; }

.records-card {
  background: #ffffff;
  border: 1px solid #eef2f6;
  border-radius: 14px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}
.records-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
}
.records-table thead th {
  text-align: left;
  font-size: 11.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94a3b8;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #eef2f6;
}
.records-table tbody tr {
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  transition: background 0.12s ease;
}
.records-table tbody tr:last-child { border-bottom: 0; }
.records-table tbody tr:hover { background: #f8fafc; }
.records-table td { padding: 12px 16px; color: #0f172a; vertical-align: middle; }
.td-meta { color: #475569; font-size: 13px; }
.td-num { font-family: ui-monospace, monospace; font-size: 12.5px; color: #475569; }
.id-cell {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  background: #f1f5f9;
  color: #475569;
  padding: 1px 6px;
  border-radius: 5px;
}
.algo-cell {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  color: #4338ca;
  background: #eef2ff;
  padding: 1px 6px;
  border-radius: 5px;
}
.algo-cell-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.td-empty {
  text-align: center;
  color: #94a3b8;
  padding: 40px 16px;
  font-size: 13px;
}
.td-empty .empty-icon { font-size: 28px; color: #cbd5e1; display: block; margin-bottom: 6px; }
.th-actions { text-align: right; }
.th-actions .row-action { display: none; }
.records-table tbody tr:hover .row-action { display: inline-flex; }

/* Status pills */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid;
}
.pill-dot { width: 6px; height: 6px; border-radius: 50%; }
.status-pill.status-SUCCESS { color: #047857; background: #ecfdf5; border-color: #d1fae5; }
.status-pill.status-SUCCESS .pill-dot { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.18); }
.status-pill.status-RUNNING { color: #b45309; background: #fffbeb; border-color: #fde68a; }
.status-pill.status-RUNNING .pill-dot { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18); animation: pulse 1.4s infinite; }
.status-pill.status-PENDING { color: #475569; background: #f1f5f9; border-color: #e2e8f0; }
.status-pill.status-PENDING .pill-dot { background: #94a3b8; }
.status-pill.status-FAILED { color: #be123c; background: #fef2f2; border-color: #fecdd3; }
.status-pill.status-FAILED .pill-dot { background: #f43f5e; }
.status-pill.status-DEAD { color: #6b7280; background: #f3f4f6; border-color: #e5e7eb; }
.status-pill.status-DEAD .pill-dot { background: #6b7280; }
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18); }
  50% { box-shadow: 0 0 0 6px rgba(245, 158, 11, 0.05); }
}
.enrich-tag {
  margin-left: 4px;
  font-size: 10.5px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 4px;
  background: #eef2ff;
  color: #4338ca;
}
.enrich-tag.warn { background: #fffbeb; color: #b45309; }

.row-action {
  border: 0;
  background: transparent;
  width: 28px; height: 28px;
  border-radius: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #64748b;
  margin-left: 4px;
  transition: background 0.12s ease, color 0.12s ease;
}
.row-action:hover { background: #eef2ff; color: #4f46e5; }
.row-action.warn:hover { background: #fffbeb; color: #b45309; }
.row-action .el-icon { font-size: 15px; }

.muted { color: #94a3b8; }
.small { font-size: 12px; }

/* ---- Responsive ---- */
@media (max-width: 1100px) {
  .stats { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 800px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .charts { grid-template-columns: 1fr; }
  .hero { flex-direction: column; align-items: flex-start; }
  .hero-actions { width: 100%; }
  .section-header { flex-direction: column; align-items: flex-start; }
}
</style>
