import { defineStore } from 'pinia'
import { ref } from 'vue'
import { recordsApi, algorithmsApi, type Inspection, type Algorithm, type RecordStats } from '../api/client'

export const useRecordsStore = defineStore('records', () => {
  const records = ref<Inspection[]>([])
  const algorithms = ref<Algorithm[]>([])
  const loading = ref(false)
  const total = ref(0)
  const stats = ref<RecordStats | null>(null)
  const statsLoading = ref(false)

  async function fetchRecords(params: Record<string, any> = {}) {
    loading.value = true
    try {
      const r = await recordsApi.list(params)
      records.value = r.items
      total.value = r.total
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    statsLoading.value = true
    try {
      stats.value = await recordsApi.stats()
    } finally {
      statsLoading.value = false
    }
  }

  async function fetchAlgorithms() {
    const r = await algorithmsApi.list()
    algorithms.value = r.items
  }

  async function fetchRecord(id: number) {
    return await recordsApi.get(id)
  }

  async function uploadFile(code: string, file: File, meta: Record<string, any> = {}) {
    return await recordsApi.upload(code, file, meta)
  }

  async function uploadBatch(code: string, files: File[], meta: Record<string, any> = {}) {
    return await recordsApi.uploadBatch(code, files, meta)
  }

  return { records, algorithms, loading, total, stats, statsLoading, fetchRecords, fetchStats, fetchAlgorithms, fetchRecord, uploadFile, uploadBatch }
})
