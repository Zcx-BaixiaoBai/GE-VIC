<template>
  <el-table :data="records" v-loading="loading" stripe>
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column label="状态" width="180">
      <template #default="{ row }">
        <StatusTag :status="row.status" :enrichment-status="row.enrichment_status" />
      </template>
    </el-table-column>
    <el-table-column prop="algorithm_code" label="算法" width="180" />
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
import StatusTag from './StatusTag.vue'
import type { Inspection } from '../api/client'

defineProps<{
  records: Inspection[]
  loading?: boolean
  total?: number
}>()

defineEmits<{
  (e: 'select', r: Inspection): void
  (e: 'retry', r: Inspection): void
  (e: 'refresh'): void
}>()
</script>
