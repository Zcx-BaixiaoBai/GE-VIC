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
  request_schema?: Record<string, any> | null
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

export interface LLMConfig {
  base_url: string
  model: string
  max_input_tokens: number
  max_output_tokens: number
  mock_mode: boolean
}

export interface LLMTestResult {
  success: boolean
  message: string
  model?: string | null
  content_preview?: string | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  total_tokens?: number | null
  duration_ms?: number | null
}


export interface AlgorithmUsage {
  code: string
  name: string | null
  count: number
}

export interface StatusBreakdown {
  pending: number
  running: number
  success: number
  failed: number
  dead: number
}

export interface EnrichmentBreakdown {
  enriched: number
  enriching: number
  failed: number
  pending: number
}

export interface RecordStats {
  total: number
  today_count: number
  success_rate: number
  failure_count: number
  avg_duration_ms: number | null
  p95_duration_ms: number | null
  enrichment_rate: number
  by_status: StatusBreakdown
  by_enrichment: EnrichmentBreakdown
  by_algorithm: AlgorithmUsage[]
  window_days: number
}

export const algorithmsApi = {
  list: () => api.get<{ items: Algorithm[]; total: number }>('/algorithms').then((r) => r.data),
  listAll: (includeInactive = true) =>
    api.get<Algorithm[]>('/admin/algorithms', { params: { include_inactive: includeInactive } }).then((r) => r.data),
  create: (body: Partial<Algorithm>) =>
    api.post<Algorithm>('/admin/algorithms', body).then((r) => r.data),
  update: (code: string, body: Partial<Algorithm>) =>
    api.patch<Algorithm>(`/admin/algorithms/${code}`, body).then((r) => r.data),
  remove: (code: string) => api.delete(`/admin/algorithms/${code}`).then((r) => r.data),
}

export const settingsApi = {
  getLLM: () => api.get<LLMConfig>('/settings/llm').then((r) => r.data),
  testLLM: () => api.post<LLMTestResult>('/settings/llm/test').then((r) => r.data),
}

export const recordsApi = {
  list: (params: Record<string, any> = {}) =>
    api.get<{ items: Inspection[]; total: number }>('/records', { params }).then((r) => r.data),
  stats: () => api.get<RecordStats>('/records/stats').then((r) => r.data),
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
