import { expect, test } from '@playwright/test'

import { login, navigate } from './helpers'

const pad = (value: number) => String(value).padStart(2, '0')

test('a previsão do mês aparece no Painel e na página Previsão, com o modelo base', async ({ page }) => {
  await login(page)
  const categories: Array<{ id: number; kind: string }> = await (await page.request.get('/api/categories')).json()
  const expense = categories.find((category) => category.kind === 'expense')
  const today = new Date()
  const created = await page.request.post('/api/transactions', {
    data: {
      description: 'Almoço de teste',
      kind: 'expense',
      amount_cents: 4_250,
      date: `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`,
      category_id: expense?.id,
      payment_method: 'pix',
    },
  })
  expect(created.ok()).toBe(true)
  await page.reload() // os dados criados pela API não estão no cache da tela

  await navigate(page, 'Painel')
  await expect(page.getByText('Previsão do mês')).toBeVisible()
  await expect(page.getByText(/pelo modelo base/).first()).toBeVisible()

  await navigate(page, 'Previsão')
  await expect(page.getByRole('heading', { name: 'Previsão' })).toBeVisible()
  await expect(
    page.getByText('Usando o modelo base. Rode `financeiro treinar` com pelo menos 2 meses fechados.'),
  ).toBeVisible()
})
