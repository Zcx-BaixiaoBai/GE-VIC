<template>
  <el-drawer v-model="visible" :title="`记录 #${record?.id}`" size="60%">
    <div v-if="record" v-loading="loading">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="ID">{{ record.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="record.status" :enrichment-status="record.enrichment_status" />
        </el-descriptions-item>
        <el-descriptions-item label="算法">{{ record.algorithm_code }}</el-descriptions-item>
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
        <p><strong>一句话总结:</strong> {{ record.summary }}</p>
      </div>
      <pre v-if="record.recognition" style="background: #f5f5f5; padding: 12px; border-radius: 4px;">{{ JSON.stringify(record.recognition, null, 2) }}</pre>
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
import { ref, watch } from 'vue'
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

function formatTime(t: string | null | undefined): string {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
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
