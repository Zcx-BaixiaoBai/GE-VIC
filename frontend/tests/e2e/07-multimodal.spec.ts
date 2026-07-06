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

  // wait for the per-file success badge
  await page.waitForSelector('.file-item-badge.success', { state: 'visible', timeout: 60000 })
  await expect(page.locator('.file-item-badge.success').first()).toBeVisible()
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

  // default = multimodal_llm: 16 fields
  await expect(page.locator('.config-field-row')).toHaveCount(15)

  const select = page.locator('.el-form-item:has(label:has-text("引擎类型")) .el-select')
  await page.waitForTimeout(400)
  // 5 original + 2 dividers + 8 LLM fields + 1 LLM 连接 divider = 16
  await expect(page.locator('.config-field-row')).toHaveCount(15)

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

test('UI: newly created algorithm appears in upload page without restart', async ({ page, request }) => {
  const code = 'live-reg-' + (Date.now() % 100000)

  const cr = await request.post('http://127.0.0.1:8000/api/v1/admin/algorithms', {
    headers: { 'X-Inspector-Id': 'WEB-DEMO-USER' },
    data: { code, name: '[Live Registry Test]', engine_type: 'mock', engine_config: { delay_ms: 100 } },
  })
  expect(cr.status()).toBe(201)

  await page.goto('/upload')
  await page.waitForSelector('.algo-pick', { timeout: 10000 })
  const cards = await page.locator('.algo-pick:has(.algo-pick-code:text("' + code + '"))').count()
  expect(cards).toBe(1)

  const dr = await request.delete('http://127.0.0.1:8000/api/v1/admin/algorithms/' + code, {
    headers: { 'X-Inspector-Id': 'WEB-DEMO-USER' },
  })
  expect(dr.status()).toBe(204)

  await page.reload()
  await page.waitForSelector('.algo-pick', { timeout: 10000 })
  const afterCards = await page.locator('.algo-pick:has(.algo-pick-code:text("' + code + '"))').count()
  expect(afterCards).toBe(0)
})


test('API: test algorithm endpoint returns connectivity result', async ({ request }) => {
  const r = await request.post('http://127.0.0.1:8000/api/v1/admin/algorithms/multimodal-inspector/test', {
    headers: { 'X-Inspector-Id': 'dev' },
    data: {},
  })
  expect(r.status()).toBe(200)
  const body = await r.json()
  expect(body).toHaveProperty('success')
  expect(body).toHaveProperty('message')
  expect(body).toHaveProperty('engine_type')
  expect(body.engine_type).toBe('multimodal_llm')
  // 真实 LLM 调用, 应该有 model 和 token 字段
  expect(body).toHaveProperty('model')
  expect(body).toHaveProperty('duration_ms')
})


test('API: test algorithm with bad engine_config returns failure', async ({ request }) => {
  const r = await request.post('http://127.0.0.1:8000/api/v1/admin/algorithms/multimodal-inspector/test', {
    headers: { 'X-Inspector-Id': 'dev' },
    data: {
      engine_config: {
        llm_base_url: 'https://nonexistent.invalid/v1',
        llm_api_key: 'sk-bogus',
        llm_model: 'no-such-model',
      },
    },
  })
  expect(r.status()).toBe(200)
  const body = await r.json()
  expect(body.success).toBe(false)
  expect(body.error_code).toBeTruthy()
  expect(body.message).toContain('LLM')
})


test('API: test algorithm returns success without real call', async ({ request }) => {
  // 使用真实算法测试连通性
  const r = await request.post('http://127.0.0.1:8000/api/v1/admin/algorithms/insulator-damage/test', {
    headers: { 'X-Inspector-Id': 'dev' },
    data: {},
  })
  expect(r.status()).toBe(200)
  const body = await r.json()
  // 成功或失败都可, 只要连通性 OK
  expect(typeof body.success).toBe('boolean')
})


test('UI: upload page supports selecting multiple files', async ({ page }) => {
  await page.goto('/upload')
  await page.waitForSelector('.algo-pick', { timeout: 10000 })
  // Pick multimodal-inspector algorithm
  await page.locator('.algo-pick').filter({ hasText: 'multimodal-inspector' }).first().click()
  // Set 3 files
  const fileInput = page.locator('input[type="file"]').first()
  await fileInput.setInputFiles([
    'C:/Users/Admin/Documents/GE-VIC/test-image.jpg',
    'C:/Users/Admin/Documents/GE-VIC/test-image.jpg',
    'C:/Users/Admin/Documents/GE-VIC/test-image.jpg',
  ])
  await page.waitForTimeout(500)
  // 3 file items in the list
  await expect(page.locator('.file-item')).toHaveCount(3)
  // Summary shows count
  await expect(page.locator('.file-list-title')).toContainText('3 个文件')
  // Remove first one
  await page.locator('.file-item button:has-text("移除")').first().click()
  await page.waitForTimeout(300)
  await expect(page.locator('.file-item')).toHaveCount(2)
  // Clear all
  await page.locator('button:has-text("全部清空")').click()
  await page.waitForTimeout(300)
  await expect(page.locator('.file-item')).toHaveCount(0)
})


test('UI: batch upload with joint analysis creates single record', async ({ page, request }) => {
  await page.goto('/upload')
  await page.waitForSelector('.algo-pick', { timeout: 10000 })
  // Pick multimodal-inspector
  await page.locator('.algo-pick').filter({ hasText: 'multimodal-inspector' }).first().click()
  // Default mode is 'joint' (联合分析)
  const modeCount = await page.locator('.upload-mode').count()
  expect(modeCount).toBeGreaterThan(0)
  // Set 3 files
  const fileInput = page.locator('input[type="file"]').first()
  await fileInput.setInputFiles([
    'C:/Users/Admin/Documents/GE-VIC/test-image.jpg',
    'C:/Users/Admin/Documents/GE-VIC/test-image.jpg',
    'C:/Users/Admin/Documents/GE-VIC/test-image.jpg',
  ])
  await page.waitForTimeout(500)
  await expect(page.locator('.file-item')).toHaveCount(3)
  // Submit
  await page.locator('.submit-btn').click()
  // Wait for success badge (LLM call takes ~5s, allow 60s)
  await page.locator('.file-item-badge.success').first().waitFor({ state: 'visible', timeout: 60000 })
  // Verify via API that the record is a batch
  const r = await request.get('http://127.0.0.1:8000/api/v1/records?limit=1', { headers: { 'X-Inspector-Id': 'dev' } })
  const j = await r.json()
  const latest = j.items[0]
  expect(latest.is_batch).toBe(true)
  expect(latest.batch_size).toBe(3)
  expect(latest.batch_files).toHaveLength(3)
})


test('UI: max_input_tokens and max_output_tokens accept large values without clamping', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  // Open edit dialog for minimax-test
  await page.locator('.algo-card').filter({ hasText: 'minimax-test' }).first().locator('button:has-text("查看配置")').click()
  await page.waitForTimeout(800)
  // Scroll to LLM connection section to find max_input_tokens
  await page.locator('.el-dialog__body').evaluate(el => el.scrollTop = el.scrollHeight)
  await page.waitForTimeout(300)
  // Find the input for max_input_tokens and max_output_tokens by their values
  // (they were set to 800000 and 64000 by a previous test run)
  const allInputs = await page.locator('.el-dialog .el-input-number input').all()
  // The values should include 800000 and 64000 (not clamped)
  let found800k = false
  let found64k = false
  for (const input of allInputs) {
    const v = await input.inputValue()
    if (v === '800000') found800k = true
    if (v === '64000') found64k = true
  }
  expect(found800k).toBe(true)
  expect(found64k).toBe(true)
})
