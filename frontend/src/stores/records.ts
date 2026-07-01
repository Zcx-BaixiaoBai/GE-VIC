import { defineStore } from 'pinia'
import { ref } from 'vue'
import { algorithmsApi, recordsApi, type Algorithm, type Inspection } from '../api/client'

export const useRecordsStore = defineStore('records', () => {
  const records = ref<Inspection[]>([])
  const algorithms = ref<Algorithm[]>([])
  const loading = ref(false)
  const total = ref(0)

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

  return { records, algorithms, loading, total, fetchRecords, fetchAlgorithms, fetchRecord, uploadFile }
})
