import { expect, test } from '@playwright/test'

import { login, navigate, STATEMENT_PDF } from './helpers'

interface Transaction {
  description: string
  kind: string
  amount_cents: number
  payment_method: string
}

test('importar extrato: entrada vira receita, não lançar tira um Pix e confirmar cria o lançamento', async ({
  page,
}) => {
  await login(page)
  await navigate(page, 'Importar')
  await page.getByRole('radiogroup', { name: 'Tipo de arquivo' }).getByText('Extrato da conta').click()
  await expect(page.getByLabel('Cartão', { exact: true })).toHaveCount(0)
  await page.getByLabel('Arquivo do extrato (PDF)').setInputFiles(STATEMENT_PDF)
  await page.getByRole('button', { name: 'Ler extrato' }).click()

  await expect(page.getByRole('heading', { name: 'Extrato Nubank' })).toBeVisible()
  await expect(page.getByText('Soma confere com os totais impressos no extrato.')).toBeVisible()
  await expect(page.getByText('Em standby (3)')).toBeVisible()

  const income = page.getByLabel('Categoria de EMPRESA EXEMPLO LTDA (entrada)')
  await expect(income.locator('option', { hasText: 'Lazer' })).toHaveCount(0)
  const salary = await income.locator('option', { hasText: 'Salário' }).getAttribute('value')
  await income.selectOption(salary ?? '')
  await page.getByRole('listitem').filter({ has: income }).getByRole('button', { name: 'Resolver' }).click()
  await expect(page.getByText('Em standby (2)')).toBeVisible()

  await page.getByRole('button', { name: 'Não lançar CARLOS PEREIRA' }).click()
  await expect(page.getByText('Em standby (1)')).toBeVisible()
  await page.getByText('Fora da importação (1)').click()
  await expect(page.getByText('Você escolheu não lançar')).toBeVisible()

  await page.getByRole('button', { name: 'Confirmar 1' }).click()
  await expect(page.getByText('Lançamentos criados.')).toBeVisible()
  const response = await page.request.get('/api/transactions?month=2026-10')
  const transactions = ((await response.json()) as Transaction[]).filter(
    (item) => item.description === 'EMPRESA EXEMPLO LTDA',
  )
  expect(transactions.map(({ kind, amount_cents, payment_method }) => [kind, amount_cents, payment_method])).toEqual([
    ['income', 150000, 'pix'],
  ])
})
