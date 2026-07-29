import { expect, test } from '@playwright/test'

test('logs in and opens the match review workspace', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('管理员密码').fill('change-me')
  await page.getByRole('button', { name: '进入控制台' }).click()

  await expect(page.getByRole('heading', { name: '媒体整理总览' })).toBeVisible()
  await page.getByRole('link', { name: '匹配审核' }).click()
  await expect(page.getByRole('heading', { name: 'AI 识别与 TMDB 匹配' })).toBeVisible()
  await expect(page.getByText('三体.Three.Body.2023.E03.2160p.WEB-DL.mkv')).toBeVisible()
})
