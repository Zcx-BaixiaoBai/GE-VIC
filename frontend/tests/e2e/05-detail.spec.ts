import { test, expect } from '@playwright/test'

test('UI: upload view loads', async ({ page }) => {
  await page.goto('/upload')
  await expect(page.getByRole('heading', { name: '上传识别' })).toBeVisible()
  await expect(page.getByText('选择算法')).toBeVisible()
})
