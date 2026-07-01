import { test, expect } from '@playwright/test'

test('API: missing X-Inspector-Id returns 400', async ({ request }) => {
  const r = await request.post('http://localhost:8000/api/v1/inspect/insulator-damage', {
    multipart: { file: { name: 'test.jpg', mimeType: 'image/jpeg', buffer: Buffer.from('fake') } },
  })
  expect(r.status()).toBe(400)
})
