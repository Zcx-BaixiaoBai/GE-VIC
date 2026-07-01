import { test, expect } from '@playwright/test'

test('UI: settings page loads with algorithm list', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
  await expect(page.getByText('算法配置').first()).toBeVisible()
  // wait for algorithms to load
  await page.waitForSelector('table tbody tr', { timeout: 10000 })
  // verify the seeded algorithms are visible
  await expect(page.getByText('insulator-damage').first()).toBeVisible()
  await expect(page.getByText('insulator-demo').first()).toBeVisible()
})

test('UI: LLM tab shows config and test button', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: '系统设置' })).toBeVisible()
  await page.getByRole('tab', { name: 'LLM 模型' }).click()
  await expect(page.getByText('LLM 富化服务配置')).toBeVisible()
  // wait for config to load (look for base_url label)
  await expect(page.getByText('Base URL')).toBeVisible({ timeout: 5000 })
  await expect(page.getByText('Mock Mode')).toBeVisible()
  // the test button should be present
  await expect(page.getByRole('button', { name: /运行测试|再次测试/ })).toBeVisible()
})

test('UI: open algorithm create dialog', async ({ page }) => {
  await page.goto('/settings')
  await page.waitForSelector('table tbody tr', { timeout: 10000 })
  await page.getByRole('button', { name: '+ 新增算法' }).click()
  // dialog title (also matches the button label, so use heading role)
  await expect(page.getByRole('heading', { name: '新增算法' })).toBeVisible()
  // form fields
  await expect(page.getByLabel('Code', { exact: true })).toBeVisible()
  await expect(page.getByLabel('名称', { exact: true })).toBeVisible()
})
