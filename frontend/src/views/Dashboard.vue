<template>
  <div>
    <h2>仪表盘</h2>
    <el-card>
      <RecordList
        :records="store.records"
        :loading="store.loading"
        :total="store.total"
        @select="onSelect"
        @retry="onRetry"
        @refresh="onRefresh"
      />
    </el-card>
    <RecordDetail v-model="drawerVisible" :record="selectedRecord" @refresh="store.fetchRecords()" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRecordsStore } from '../stores/records'
import { recordsApi, type Inspection } from '../api/client'
import RecordList from '../components/RecordList.vue'
import RecordDetail from '../components/RecordDetail.vue'
import { ElMessage } from 'element-plus'

const store = useRecordsStore()
const drawerVisible = ref(false)
const selectedRecord = ref<Inspection | null>(null)

onMounted(async () => {
  await store.fetchRecords()
})

async function onSelect(r: Inspection) {
  selectedRecord.value = await store.fetchRecord(r.id)
  drawerVisible.value = true
}

async function onRetry(r: Inspection) {
  await recordsApi.retry(r.id)
  ElMessage.success('重试已提交')
  await store.fetchRecords()
}

async function onRefresh() {
  await store.fetchRecords()
}
</script>
