import { test, expect } from '@playwright/test'

test('UI: dashboard loads with stats and records', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()
  // 6 stat cards
  await expect(page.locator('.stat-card')).toHaveCount(6)
  // status distribution chart
  await expect(page.getByText('状态分布').first()).toBeVisible()
  // algorithm usage ranking
  await expect(page.getByText('算法使用排行')).toBeVisible()
  // records table loads
  await page.waitForFunction(
    () => document.querySelectorAll('.records-table tbody tr').length >= 1,
    { timeout: 10000 }
  )
  await expect(page.locator('.records-table thead th')).toHaveCount(8)
})

test('UI: dashboard stats have real values from backend', async ({ page }) => {
  await page.goto('/')
  // wait for the first stat value to be a real number (not em-dash)
  await page.waitForFunction(
    () => {
      const v = document.querySelector('.stat-card .stat-value')?.textContent?.trim() || ''
      return /^\d+$/.test(v)
    },
    { timeout: 10000 }
  )
  const totalText = await page.locator('.stat-card').first().locator('.stat-value').textContent()
  const total = parseInt(totalText || '0', 10)
  expect(total).toBeGreaterThan(0)
})

test('UI: dashboard status filter opens and shows options', async ({ page }) => {
  await page.goto('/')
  await page.waitForSelector('.header-actions .el-select', { timeout: 10000 })
  await page.locator('.header-actions .el-select').first().click()
  await expect(page.getByRole('option', { name: '等待中' })).toBeVisible()
  await expect(page.getByRole('option', { name: '成功' })).toBeVisible()
  await expect(page.getByRole('option', { name: '失败' })).toBeVisible()
})
