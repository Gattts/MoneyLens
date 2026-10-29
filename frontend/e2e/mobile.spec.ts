import { expect, test } from '@playwright/test'

import { createTransaction, login, navigate, unique } from './helpers'

test('no celular, o menu abre, navega e dá para lançar um gasto', async ({ page }) => {
  await login(page)
  await page.getByRole('button', { name: 'Abrir menu' }).click()
  await navigate(page, 'Lançamentos')
  await expect(page.getByRole('heading', { name: 'Lançamentos' })).toBeVisible()
  await createTransaction(page, unique('Café'), '7,50', '🍽️ Comida fora')
})

for (const path of [
  '/',
  '/lancamentos',
  '/fixas',
  '/cartoes',
  '/faturas',
  '/metas',
  '/categorias',
  '/anual',
  '/previsao',
  '/configuracoes',
  '/usuarios',
]) {
  test(`sem rolagem horizontal no celular em ${path}`, async ({ page }) => {
    await login(page)
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })
}
