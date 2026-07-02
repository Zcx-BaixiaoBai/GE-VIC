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

test('UI: create dialog uses dynamic form fields per engine type', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  await page.getByRole('button', { name: '新增算法' }).click()
  await page.waitForSelector('.settings-dialog', { timeout: 5000 })

  // default = mock: 2 fields
  await expect(page.locator('.config-field-row')).toHaveCount(2)

  // switch to multimodal
  const select = page.locator('.el-form-item:has(label:has-text("引擎类型")) .el-select')
  await select.click()
  await page.getByRole('option', { name: /多模态 LLM/ }).click()
  await page.waitForTimeout(400)
  // 5 fields
  await expect(page.locator('.config-field-row')).toHaveCount(5)

  // switch to cloud_api
  await select.click()
  await page.getByRole('option', { name: /Cloud API/ }).click()
  await page.waitForTimeout(400)
  // 6 fields
  await expect(page.locator('.config-field-row')).toHaveCount(6)
  // sensitive tag exists
  await expect(page.locator('.sensitive-tag').first()).toBeVisible()

  // advanced JSON toggle
  await page.getByRole('button', { name: /高级|返回表单/ }).click()
  await page.waitForTimeout(300)
  await expect(page.locator('.json-input')).toBeVisible()
  await page.getByRole('button', { name: /返回表单/ }).click()
  await page.waitForTimeout(300)
  await expect(page.locator('.config-field-row')).toHaveCount(6)

  // close
  await page.keyboard.press('Escape')
})

test('UI: multimodal form submission persists custom config', async ({ page, request }) => {
  const stamp = Date.now() % 100000
  const code = 'mm-form-e2e-' + stamp
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  await page.getByRole('button', { name: '新增算法' }).click()
  await page.waitForSelector('.settings-dialog', { timeout: 5000 })
  await page.locator('.el-form-item:has(label:has-text("Code")) input').fill(code)
  await page.locator('.el-form-item:has(label:has-text("名称")) input').fill('[E2E] 多模态表单')
  const select = page.locator('.el-form-item:has(label:has-text("引擎类型")) .el-select')
  await select.click()
  await page.getByRole('option', { name: /多模态 LLM/ }).click()
  await page.waitForTimeout(400)
  // change extract_frames via number input
  const efInput = page.locator('.config-field-row').first().locator('.el-input-number input')
  await efInput.fill('5')
  await page.getByRole('button', { name: '创建算法' }).click()
  await page.waitForTimeout(2000)

  // verify via API (list then find)
  const r = await request.get('http://127.0.0.1:8000/api/v1/admin/algorithms?include_inactive=true', {
    headers: { 'X-Inspector-Id': 'WEB-DEMO-USER' },
  })
  expect(r.status()).toBe(200)
  const list = await r.json()
  const body = list.find((a: any) => a.code === code)
  expect(body.code).toBe(code)
  expect(body.engine_type).toBe('multimodal_llm')
  expect(body.engine_config.extract_frames).toBe(5)
  // temperature is the default 0.3
  expect(body.engine_config.temperature).toBe(0.3)

  // cleanup
  await request.delete('http://127.0.0.1:8000/api/v1/admin/algorithms/' + code, {
    headers: { 'X-Inspector-Id': 'WEB-DEMO-USER' },
  })
})
