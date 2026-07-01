import { test, expect } from '@playwright/test'

test('API: unknown algorithm_code returns 400', async ({ request }) => {
  const r = await request.post('http://localhost:8000/api/v1/inspect/nonexistent', {
    headers: { 'X-Inspector-Id': 'E2E-001' },
    multipart: { file: { name: 'test.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('fake') } },
  })
  expect(r.status()).toBe(400)
})
