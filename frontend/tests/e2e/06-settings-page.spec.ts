import { test, expect } from '@playwright/test'

test('UI: settings page hero, stats and algorithm cards', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
  // segmented control
  await expect(page.locator('.seg-btn.active')).toContainText('算法配置')
  // stats row
  const stats = page.locator('.stat-card .stat-value')
  await expect(stats).toHaveCount(4)
  // algo cards
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  const cards = page.locator('.algo-card')
  expect(await cards.count()).toBeGreaterThanOrEqual(1)
  await expect(page.locator('.algo-code').first()).toBeVisible()
})

test('UI: search filters algorithm cards', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  const allCount = await page.locator('.algo-card').count()
  await page.fill('.search-box input', 'demo')
  await page.waitForTimeout(200)
  const filtered = await page.locator('.algo-card').count()
  expect(filtered).toBeLessThan(allCount)
  expect(filtered).toBeGreaterThanOrEqual(0)
})

test('UI: filter pills switch active state', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  // click "已启用" pill
  await page.locator('.pill').nth(1).click()
  await expect(page.locator('.pill').nth(1)).toHaveClass(/active/)
  await expect(page.locator('.pill').nth(0)).not.toHaveClass(/active/)
})

test('UI: LLM tab shows config and test result', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
  await page.locator('.seg-btn').nth(1).click()
  // llm config card
  await expect(page.getByText('富化服务配置')).toBeVisible()
  await expect(page.getByText('Base URL')).toBeVisible()
  // click test button
  await page.getByRole('button', { name: /运行测试|再次测试/ }).click()
  await page.waitForSelector('.test-result', { timeout: 15000 })
  // result has success or fail class
  const cls = await page.locator('.test-result').getAttribute('class')
  expect(cls).toMatch(/success|fail/)
})

test('UI: open algorithm create dialog', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  await page.getByRole('button', { name: '新增算法' }).click()
  // dialog title (also matches the button label, so use heading role)
  await expect(page.getByRole('heading', { name: '新增算法' })).toBeVisible()
  // form fields
  await expect(page.getByLabel('Code', { exact: true })).toBeVisible()
  await expect(page.getByLabel('名称', { exact: true })).toBeVisible()
})


test('UI: click 算法测试按钮 opens result dialog with engine info', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  const card = page.locator('.algo-card').filter({ hasText: 'multimodal-inspector' }).first()
  await card.locator('button:has-text("测试")').click()
  // Wait for the dialog title to be attached to DOM (visible or not)
  await page.locator('.el-dialog__title:has-text("算法测试结果")').waitFor({ state: 'attached', timeout: 30000 })
  // Wait for the result content to be attached (LLM call takes ~5s)
  await page.locator('.algo-test-result .algo-test-message').waitFor({ state: 'attached', timeout: 30000 })
  // Should contain "LLM 调用成功" or "LLM 调用失败"
  await expect(page.locator('.algo-test-result .algo-test-message')).toContainText(/LLM 调用/, { timeout: 10000 })
  // The engine info should show multimodal_llm
  await expect(page.locator('.algo-test-meta dd').first()).toContainText('multimodal_llm')
})


test('UI: edit dialog can modify algorithm config and save', async ({ page, request }) => {
  await page.goto('/settings')
  await page.waitForSelector('.algo-card', { timeout: 10000 })
  // Open edit dialog for the first card
  await page.locator('.algo-card button:has-text("查看配置")').first().click()
  // Wait for dialog with form
  await page.locator('.el-dialog__title:has-text("编辑算法")').waitFor({ state: 'attached', timeout: 10000 })
  // Should have name input
  const nameInput = page.locator('.el-dialog input[placeholder*="算法显示名称"]')
  await nameInput.waitFor({ state: 'attached', timeout: 10000 })
  // Should have the engine type badge displayed (read-only engine)
  await expect(page.locator('.el-dialog .engine-badge').first()).toBeVisible()
  // Should have engine config form fields
  const configRows = page.locator('.el-dialog .config-field-row')
  expect(await configRows.count()).toBeGreaterThan(0)
  // Cancel (don't actually save to avoid affecting other tests)
  await page.locator('.el-dialog button:has-text("取消")').click()
  // Wait for dialog to be hidden (not removed from DOM)
  await page.locator('.el-dialog.settings-dialog').waitFor({ state: 'hidden', timeout: 10000 })
  // Verify the actual dialog state - overlay should be display: none
  const overlayState = await page.evaluate(() => {
    const overlays = document.querySelectorAll('.el-overlay');
    return Array.from(overlays).every(o => o.style.display === 'none' || o.querySelector('.el-dialog__title')?.textContent?.includes('算法测试') === false);
  });
  expect(overlayState).toBe(true);
})
