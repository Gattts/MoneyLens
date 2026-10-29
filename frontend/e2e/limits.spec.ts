import { expect, test } from '@playwright/test'

import { login, navigate, unique } from './helpers'

const pad = (value: number) => String(value).padStart(2, '0')

// Passar de 100% dá o aviso mais grave, qualquer que seja a previsão do modelo base (a 90%, o "vai estourar" ganha).
test('um teto criado na tela avisa no Painel e no sino quando o gasto passa dele', async ({ page }) => {
  await login(page)
  const name = unique('Teto E2E')
  const created = await page.request.post('/api/categories', {
    data: { name, icon: '', kind: 'expense', default_bucket: 'wants' },
  })
  expect(created.ok()).toBe(true)
  const category: { id: number } = await created.json()
  await page.reload() // a categoria criada pela API não está no cache da tela

  await navigate(page, 'Tetos')
  await page.getByRole('button', { name: 'Novo teto' }).first().click()
  await page.getByLabel('Categoria').selectOption({ label: name })
  await expect(page.getByText('Sem histórico ainda: informe o valor. Depois do primeiro mês eu sugiro.')).toBeVisible()
  await page.getByLabel('Valor do teto').fill('100,00')
  await page.getByRole('button', { name: 'Salvar' }).click()
  const card = page.locator('[data-limit]').filter({ hasText: name })
  await expect(card.getByText('0%')).toBeVisible()

  const today = new Date()
  const spent = await page.request.post('/api/transactions', {
    data: {
      description: 'Jantar de teste',
      kind: 'expense',
      amount_cents: 10_500,
      date: `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`,
      category_id: category.id,
      payment_method: 'pix',
    },
  })
  expect(spent.ok()).toBe(true)
  await page.reload()

  await navigate(page, 'Painel')
  const message = new RegExp(`${name} passou do teto`)
  await expect(page.getByText(message).first()).toBeVisible()
  const bell = page.locator('aside').getByRole('button', { name: 'Alertas de teto' })
  await expect(bell).toContainText('1')
  await bell.click()
  await expect(page.getByRole('dialog').getByText(message)).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(bell).not.toContainText('1')
})
