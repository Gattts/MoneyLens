import { expect, type Page, test } from '@playwright/test'

import { login, monthParam, unique } from './helpers'

const pad = (value: number) => String(value).padStart(2, '0')
const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
const shortMonth = (month: string) => `${MONTHS[Number(month.slice(5)) - 1]}/${month.slice(0, 4)}`

async function created<T>(page: Page, url: string, data: object): Promise<T> {
  const response = await page.request.post(url, { data })
  expect(response.ok(), await response.text()).toBe(true)
  return (await response.json()) as T
}

const section = (page: Page, title: string) =>
  page.locator('[data-slot="card"]').filter({ has: page.getByText(title, { exact: true }) })

test('compra no cartão conta no mês em que a fatura vence: Painel, "Para pagar depois" e Tetos', async ({ page }) => {
  await login(page)
  const today = new Date()
  const day = today.getDate()
  // Fecha hoje: a compra de hoje vai para a fatura seguinte. Vencendo depois do fechamento, é paga no mês seguinte;
  // a partir do dia 28 não há vencimento depois do fechamento, e ela é paga dois meses depois.
  const [dueDay, offset] = day < 28 ? [28, 1] : [1, 2]
  const paidIn = monthParam(offset)
  const cardName = unique('Cartão caixa')
  const categoryName = unique('Categoria caixa')
  const card = await created<{ id: number }>(page, '/api/cards', {
    name: cardName,
    limit_cents: 300_000,
    closing_day: day,
    due_day: dueDay,
  })
  const category = await created<{ id: number }>(page, '/api/categories', {
    name: categoryName,
    icon: '',
    kind: 'expense',
    default_bucket: 'wants',
  })
  await created(page, '/api/limits', { category_id: category.id, amount_cents: 10_000 })
  await created(page, '/api/transactions', {
    description: 'Compra no cartão',
    kind: 'expense',
    amount_cents: 9_500,
    date: `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(day)}`,
    category_id: category.id,
    payment_method: 'credit_card',
    card_id: card.id,
  })
  await page.reload()

  // Mês atual: a compra aparece em "Para pagar depois" e não entra nas categorias do mês.
  const later = section(page, 'Para pagar depois').locator('li').filter({ hasText: cardName })
  await expect(later).toContainText(new RegExp(`95,00 · entra em ${shortMonth(paidIn).replace('/', '\\/')}`))
  await expect(section(page, 'Para onde foi o dinheiro').getByText(categoryName)).toHaveCount(0)

  // Mês em que a fatura vence: entra no Painel e no teto.
  await page.goto(`/?mes=${paidIn}`)
  await expect(section(page, 'Para onde foi o dinheiro').getByText(categoryName)).toBeVisible()
  await page.goto(`/tetos?mes=${paidIn}`)
  await expect(page.locator('[data-limit]').filter({ hasText: categoryName }).getByText('95%')).toBeVisible()
})
