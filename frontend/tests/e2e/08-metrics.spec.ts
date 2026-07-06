import { test, expect } from '@playwright/test'

test('API: /metrics returns Prometheus text format with 3 core metrics', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/metrics')
  expect(r.status()).toBe(200)
  expect(r.headers()['content-type']).toMatch(/text\/plain/)

  const body = await r.text()
  // 主规范 §14.3 要求的 3 个核心指标
  expect(body).toContain('gevic_inspections_total')
  expect(body).toContain('gevic_inspection_duration_seconds')
  expect(body).toContain('gevic_engine_call_errors_total')

  // 辅助指标 (§1.7 SLO 验证)
  expect(body).toContain('gevic_upload_duration_seconds')
  expect(body).toContain('gevic_dependency_up')
  expect(body).toContain('gevic_algorithms_count')
  expect(body).toContain('gevic_http_requests_total')
  expect(body).toContain('gevic_enrichment_total')
  expect(body).toContain('gevic_llm_tokens_total')
  expect(body).toContain('gevic_process_start_time_seconds')

  // HELP / TYPE 注释
  expect(body).toContain('# HELP')
  expect(body).toContain('# TYPE')
})

test('API: /health/live returns alive', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/health/live')
  expect(r.status()).toBe(200)
  const body = await r.json()
  expect(body.status).toBe('alive')
})

test('API: /health/ready returns ready when DB+MinIO+Redis are up', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/health/ready')
  expect(r.status()).toBe(200)
  const body = await r.json()
  expect(['ready', 'degraded']).toContain(body.status)
  expect(body.checks).toBeDefined()
  expect(body.checks.database).toBeDefined()
  expect(body.checks.minio).toBeDefined()
  expect(body.checks.redis).toBeDefined()
})

test('API: /metrics includes gevic_algorithms_count > 0', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/metrics')
  const body = await r.text()
  const m = body.match(/^gevic_algorithms_count\s+(\d+(?:\.\d+)?)$/m)
  expect(m).toBeTruthy()
  expect(parseFloat(m![1])).toBeGreaterThan(0)
})

test('API: /metrics includes gevic_dependency_up labels (postgres, minio, redis)', async ({ request }) => {
  // 触发 /health/ready 设置 DEPENDENCY_UP 值
  await request.get('http://127.0.0.1:8000/health/ready')
  const r = await request.get('http://127.0.0.1:8000/metrics')
  const body = await r.text()
  expect(body).toMatch(/^gevic_dependency_up\{component="postgres"\}\s+1/m)
  expect(body).toMatch(/^gevic_dependency_up\{component="minio"\}\s+1/m)
  expect(body).toMatch(/^gevic_dependency_up\{component="redis"\}\s+1/m)
})

test('API: /metrics includes gevic_http_requests_total with endpoint labels', async ({ request }) => {
  await request.get('http://127.0.0.1:8000/health/live')
  await request.get('http://127.0.0.1:8000/api/v1/algorithms', {
    headers: { 'X-Inspector-Id': 'e2e-tester' },
  })
  const r = await request.get('http://127.0.0.1:8000/metrics')
  const body = await r.text()
  expect(body).toMatch(/gevic_http_requests_total\{endpoint="\/api\/v1\/algorithms"/)
})

test('API: /metrics includes gevic_process_start_time_seconds for SLO uptime', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/metrics')
  const body = await r.text()
  // Unix timestamp (positive, > 1.5e9 = after 2017)
  const m = body.match(/^gevic_process_start_time_seconds\s+([0-9.eE+-]+)$/m)
  expect(m).toBeTruthy()
  const ts = parseFloat(m![1])
  expect(ts).toBeGreaterThan(1.5e9)
  // Uptime is small (process started within last few minutes during test)
  const uptime = (Date.now() / 1000) - ts
  expect(uptime).toBeGreaterThan(0)
  expect(uptime).toBeLessThan(86400) // Less than 24 hours
})
