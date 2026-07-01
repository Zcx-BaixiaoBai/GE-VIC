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
