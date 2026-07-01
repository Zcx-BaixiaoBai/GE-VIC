<template>
  <el-tag :type="tagType" :effect="effect" size="small">{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status: string
  enrichmentStatus?: string | null
}>()

const label = computed(() => {
  const map: Record<string, string> = {
    PENDING: '等待中',
    RUNNING: '识别中',
    SUCCESS: '成功',
    FAILED: '失败',
    DEAD: '已停止',
    ENRICHING: '富化中',
    ENRICHED: '已富化',
    ENRICH_FAILED: '富化失败',
  }
  let s = map[props.status] || props.status
  if (props.status === 'SUCCESS' && props.enrichmentStatus === 'ENRICH_FAILED') s += ' (富化失败)'
  else if (props.status === 'SUCCESS' && props.enrichmentStatus === 'ENRICHED') s += ' (已富化)'
  return s
})

const tagType = computed(() => {
  const m: Record<string, string> = {
    PENDING: 'info',
    RUNNING: 'warning',
    SUCCESS: 'success',
    FAILED: 'danger',
    DEAD: 'danger',
    ENRICHING: 'warning',
    ENRICHED: 'success',
    ENRICH_FAILED: 'warning',
  }
  return m[props.status] || 'info'
})

const effect = computed(() => (props.status === 'RUNNING' ? 'dark' : 'light'))
</script>
