<template>
  <el-table :data="records" v-loading="loading" stripe>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column label="状态" width="180">
      <template #default="{ row }">
        <StatusTag :status="row.status" :enrichment-status="row.enrichment_status" />
      </template>
    </el-table-column>
    <el-table-column label="算法" width="220">
      <template #default="{ row }">
        <div class="algo-cell-group">
          <code class="algo-cell">{{ row.algorithm_code }}</code>
          <EngineBadge :type="engineTypeOf(row.algorithm_code)" />
        </div>
      </template>
    </el-table-column>
    <el-table-column prop="category" label="类别" width="100" />
    <el-table-column prop="asset_id" label="资产" width="140">
      <template #default="{ row }">{{ row.asset_id || row.request_meta?.asset_id || '-' }}</template>
    </el-table-column>
    <el-table-column prop="inspector_id" label="巡检员" width="110">
      <template #default="{ row }">{{ row.inspector_id || row.request_meta?.inspector_id || '-' }}</template>
    </el-table-column>
    <el-table-column label="提交时间" width="170">
      <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
    </el-table-column>
    <el-table-column label="耗时" width="80">
      <template #default="{ row }">{{ row.duration_ms ? `${row.duration_ms}ms` : '-' }}</template>
    </el-table-column>
    <el-table-column label="操作" width="180" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click="$emit('select', row)">查看</el-button>
        <el-button
          v-if="['FAILED', 'DEAD'].includes(row.status)"
          size="small"
          type="warning"
          @click="$emit('retry', row)"
        >重试</el-button>
      </template>
    </el-table-column>
  </el-table>
  <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
    <span style="color: #909399;">共 {{ total }} 条</span>
    <el-button size="small" @click="$emit('refresh')">刷新</el-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatusTag from './StatusTag.vue'
import EngineBadge from './EngineBadge.vue'
import type { Inspection, Algorithm } from '../api/client'

const props = defineProps<{
  records: Inspection[]
  loading?: boolean
  total?: number
  algorithms?: Algorithm[]
}>()

defineEmits<{
  (e: 'select', r: Inspection): void
  (e: 'retry', r: Inspection): void
  (e: 'refresh'): void
}>()

function engineTypeOf(code: string): string {
  const a = (props.algorithms || []).find((x) => x.code === code)
  return a ? a.engine_type : ''
}
</script>

<style scoped>
.algo-cell-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.algo-cell { font-family: ui-monospace, monospace; font-size: 12px; color: #4338ca; background: #eef2ff; padding: 1px 6px; border-radius: 5px; }
</style>
