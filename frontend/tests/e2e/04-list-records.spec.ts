import { test, expect } from '@playwright/test'

test('UI: dashboard loads', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible({ timeout: 10000 })
})
