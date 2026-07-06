<template>
  <span :class="['engine-badge', `engine-${type}`]" :title="title">
    <span class="engine-dot"></span>
    <span>{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  type: string
}>()

const labels: Record<string, string> = {
  cloud_api: '云 API',
  mock: 'Mock',
  hikvision_brain: '海康超脑',
  local_model: '本地模型',
  multimodal_llm: '多模态 LLM',
}

const label = computed(() => labels[props.type] || props.type || '未知引擎')

const title = computed(() => {
  if (props.type === 'mock') return 'Mock 引擎'
  if (props.type === 'multimodal_llm') return '真实 LLM 视觉识别'
  if (props.type === 'cloud_api') return '真实云端识别 API'
  if (props.type === 'local_model') return '真实本地模型推理'
  if (props.type === 'hikvision_brain') return '真实海康设备识别'
  return props.type
})
</script>

<style scoped>
.engine-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  line-height: 1.4;
  white-space: nowrap;
}
.engine-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.engine-cloud_api { color: #4f46e5; background: #eef2ff; border-color: #c7d2fe; }
.engine-cloud_api .engine-dot { background: #6366f1; }

.engine-multimodal_llm { color: #6d28d9; background: #f5f3ff; border-color: #ddd6fe; }
.engine-multimodal_llm .engine-dot { background: #8b5cf6; }

.engine-hikvision_brain { color: #b45309; background: #fffbeb; border-color: #fde68a; }
.engine-hikvision_brain .engine-dot { background: #f59e0b; }

.engine-local_model { color: #0e7490; background: #ecfeff; border-color: #cffafe; }
.engine-local_model .engine-dot { background: #06b6d4; }

/* Mock: 警示色 (琥珀), 明确区别于 SUCCESS 的绿色 */
.engine-mock {
  color: #92400e;
  background: #fef3c7;
  border-color: #fde68a;
  border-style: dashed;
}
.engine-mock .engine-dot { background: #d97706; }
</style>
