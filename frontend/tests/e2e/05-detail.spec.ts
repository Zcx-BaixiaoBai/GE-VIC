import { test, expect } from '@playwright/test'

test('UI: upload view shows algorithm picker and form', async ({ page }) => {
  await page.goto('/upload')
  await expect(page.getByRole('heading', { name: '上传识别' })).toBeVisible()
  // 3 step cards
  await expect(page.locator('.card-header')).toHaveCount(3)
  await expect(page.getByRole('heading', { name: '选择算法' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '填写元数据' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '上传文件' })).toBeVisible()
  // algorithm cards rendered
  await page.waitForSelector('.algo-pick', { timeout: 10000 })
  expect(await page.locator('.algo-pick').count()).toBeGreaterThanOrEqual(1)
  // drop zone visible
  await expect(page.locator('.drop-zone')).toBeVisible()
  // submit button disabled before selection
  await expect(page.locator('.submit-btn')).toBeDisabled()
})

test('UI: upload - click algorithm card enables selection', async ({ page }) => {
  await page.goto('/upload')
  await page.waitForSelector('.algo-pick', { timeout: 10000 })
  // first algorithm
  await page.locator('.algo-pick').first().click()
  // card gets selected class
  await expect(page.locator('.algo-pick.selected').first()).toBeVisible()
})
