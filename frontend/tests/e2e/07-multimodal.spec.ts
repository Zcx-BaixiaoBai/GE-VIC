import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const ROOT = join(__dirname, '..', '..', '..')
const TEST_IMAGE = join(ROOT, 'test-image.jpg')

test('UI: upload to multimodal algorithm runs successfully', async ({ page }) => {
  // ensure test image exists
  let fileBuf: Buffer
  try {
    fileBuf = readFileSync(TEST_IMAGE)
  } catch {
    test.skip(true, 'test-image.jpg not found at repo root')
    return
  }

  await page.goto('/upload')
  await page.waitForSelector('.algo-pick', { timeout: 10000 })

  // pick multimodal-inspector
  const mmCard = page.locator('.algo-pick:has(.algo-pick-code:text-is("multimodal-inspector"))')
  await expect(mmCard).toBeVisible()
  await mmCard.click()
  await expect(mmCard).toHaveClass(/selected/)

  // set file via hidden input
  const fileInput = page.locator('input[type=file]')
  await fileInput.setInputFiles({ name: 'test.jpg', mimeType: 'image/jpeg', buffer: fileBuf })

  // submit
  await page.locator('.submit-btn').click()

  // wait for result banner
  await page.waitForSelector('.result-banner', { timeout: 30000 })
  await expect(page.locator('.result-banner strong')).toContainText('提交成功')
})

test('API: multimodal algorithm listed in /algorithms', async ({ request }) => {
  const r = await request.get('http://127.0.0.1:8000/api/v1/algorithms', {
    headers: { 'X-Inspector-Id': 'WEB-DEMO-USER' },
  })
  expect(r.status()).toBe(200)
  const body = await r.json()
  const items = body.items || body
  const codes = items.map((a: any) => a.code)
  expect(codes).toContain('multimodal-inspector')
})

test('API: /admin/algorithms allows multimodal_llm engine type', async ({ request }) => {
  const r = await request.post('http://127.0.0.1:8000/api/v1/admin/algorithms', {
    headers: { 'X-Inspector-Id': 'WEB-DEMO-USER' },
    data: {
      code: `mm-test-${Date.now()}`,
      name: '[Test] 多模态测试算法',
      engine_type: 'multimodal_llm',
      engine_config: { extract_frames: 2, temperature: 0.3 },
    },
  })
  expect(r.status()).toBe(201)
  const body = await r.json()
  expect(body.engine_type).toBe('multimodal_llm')
  // cleanup
  await request.delete(`http://127.0.0.1:8000/api/v1/admin/algorithms/${body.code}`, {
    headers: { 'X-Inspector-Id': 'WEB-DEMO-USER' },
  })
})
