import { expect, test } from '@playwright/test'

import { login, navigate, unique } from './helpers'

const pad = (value: number) => String(value).padStart(2, '0')

test('marcar a fatura fechada como paga', async ({ page }) => {
  await login(page)
  // Fecha dia 1 e vence no último dia do mês: a fatura que fechou neste mês ainda não venceu, em qualquer data.
  const name = unique('Pagar')
  const card = await (
    await page.request.post('/api/cards', { data: { name, limit_cents: 300_000, closing_day: 1, due_day: 31 } })
  ).json()
  const categories: Array<{ id: number; kind: string }> = await (await page.request.get('/api/categories')).json()
  const expense = categories.find((category) => category.kind === 'expense')
  const today = new Date()
  const previous = new Date(today.getFullYear(), today.getMonth() - 1, 15)
  const purchase = await page.request.post('/api/transactions', {
    data: {
      description: 'Compra no cartão',
      kind: 'expense',
      amount_cents: 12_345,
      date: `${previous.getFullYear()}-${pad(previous.getMonth() + 1)}-15`,
      category_id: expense?.id,
      payment_method: 'credit_card',
      card_id: card.id,
    },
  })
  expect(purchase.ok()).toBe(true)
  await page.reload() // os dados criados pela API não estão no cache da tela

  await navigate(page, 'Cartões')
  await page
    .locator('[data-slot="card"]')
    .filter({ hasText: name })
    .getByRole('button', { name: 'Ver faturas' })
    .click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Fatura anterior' }).click()
  await expect(dialog.getByText('Fechada')).toBeVisible()
  await dialog.getByRole('button', { name: 'Marcar como paga' }).click()
  await dialog.getByRole('button', { name: 'Salvar pagamento' }).click()
  await expect(dialog.getByText(`Paga em ${pad(today.getDate())}/${pad(today.getMonth() + 1)}`)).toBeVisible()
  await expect(dialog.getByText(/à mão/)).toBeVisible()
})
