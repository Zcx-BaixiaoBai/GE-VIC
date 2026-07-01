import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/api/v1', timeout: 30000 })

api.interceptors.request.use((config) => {
  const id = localStorage.getItem('inspector_id') || 'WEB-DEMO-USER'
  config.headers['X-Inspector-Id'] = id
  return config
})

api.interceptors.response.use(
  (r) => r,
  (e) => {
    const detail = e.response?.data?.detail
    const msg = detail?.message || e.message
    ElMessage.error(msg)
    return Promise.reject(e)
  }
)

export interface Algorithm {
  code: string
  name: string
  category: string | null
  engine_type: string
  is_active: boolean
  description?: string | null
  version?: number
  engine_config?: Record<string, any>
}

export interface Inspection {
  id: number
  algorithm_code: string
  category: string | null
  status: string
  enrichment_status: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  retry_count: number
  inspector_id?: string | null
  asset_id?: string | null
  request_meta?: Record<string, any> | null
  location?: Record<string, any> | null
  file?: Record<string, any> | null
  recognition?: Record<string, any> | null
  summary?: string | null
  llm_enrichment?: Record<string, any> | null
  error?: { code?: string; message?: string } | null
}

export const algorithmsApi = {
  list: () => api.get<{ items: Algorithm[]; total: number }>('/algorithms').then((r) => r.data),
}

export const recordsApi = {
  list: (params: Record<string, any> = {}) =>
    api.get<{ items: Inspection[]; total: number }>('/records', { params }).then((r) => r.data),
  get: (id: number) => api.get<Inspection>(`/records/${id}`).then((r) => r.data),
  upload: (code: string, file: File, meta: Record<string, any> = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('meta', JSON.stringify(meta))
    return api
      .post<{ record_id: number; status: string; status_url: string }>(`/inspect/${code}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
  retry: (id: number) => api.post<{ record_id: number; status: string }>(`/records/${id}/retry`).then((r) => r.data),
  enrich: (id: number) => api.post<{ record_id: number; enrichment_status: string }>(`/records/${id}/enrich`).then((r) => r.data),
}

export default api
