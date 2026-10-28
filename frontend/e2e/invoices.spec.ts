import { expect, type Page, test } from '@playwright/test'

import { createCard, INVOICE_PASSWORD, INVOICE_PDF, login, navigate, unique } from './helpers'

async function readInvoice(page: Page, cardName: string) {
  await navigate(page, 'Faturas')
  await page.getByLabel('Cartão').selectOption({ label: cardName })
  await page.getByLabel('Arquivo da fatura (PDF)').setInputFiles(INVOICE_PDF)
  await page.getByRole('button', { name: 'Ler fatura' }).click()
}

async function cardTransactions(page: Page, cardName: string) {
  const cards: Array<{ id: number; name: string }> = await (await page.request.get('/api/cards')).json()
  const card = cards.find((item) => item.name === cardName)
  const response = await page.request.get(`/api/transactions?month=2026-09&card_id=${card?.id}`)
  return (await response.json()) as unknown[]
}

// Cada teste cria o próprio cartão: a mesma fatura em outro cartão é outra importação.
test('importar fatura com senha: pede a senha, identifica, resolve o standby e confirma', async ({ page }) => {
  await login(page)
  const cardName = unique('Inter')
  await createCard(page, cardName)
  await readInvoice(page, cardName)

  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Esta fatura tem senha.')).toBeVisible()
  await dialog.getByLabel('Senha da fatura').fill('errada')
  await dialog.getByRole('button', { name: 'Abrir fatura' }).click()
  await expect(dialog.getByText('Senha incorreta.')).toBeVisible()
  await dialog.getByLabel('Senha da fatura').fill(INVOICE_PASSWORD)
  await dialog.getByRole('button', { name: 'Abrir fatura' }).click()

  await expect(page.getByText('Soma confere com o total impresso na fatura.')).toBeVisible()
  await expect(page.getByText('Identificados (1)')).toBeVisible()
  await expect(page.getByText('Em standby (1)')).toBeVisible()
  const select = page.getByLabel('Categoria de LOJA DESCONHECIDA')
  const leisure = await select.locator('option', { hasText: 'Lazer' }).getAttribute('value')
  await select.selectOption(leisure ?? '')
  await page.getByRole('button', { name: 'Resolver' }).click()
  await expect(page.getByText('Nada em standby.')).toBeVisible()

  await page.getByRole('button', { name: 'Confirmar 2' }).click()
  await expect(page.getByText('Lançamentos criados.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Desfazer importação' })).toBeVisible()
  expect(await cardTransactions(page, cardName)).toHaveLength(2)

  await navigate(page, 'Painel')
  await expect(page.getByRole('heading', { name: 'Painel' })).toBeVisible()
  await expect(page.getByText('Faturas com gastos em standby')).toHaveCount(0)
})

test('senha salva, mesma fatura de novo abre a existente e desfazer apaga os lançamentos', async ({ page }) => {
  await login(page)
  const cardName = unique('Inter')
  await createCard(page, cardName)
  await readInvoice(page, cardName)
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Senha da fatura').fill(INVOICE_PASSWORD)
  await dialog.getByLabel(`Salvar a senha no cartão ${cardName} para as próximas faturas`).check()
  await dialog.getByRole('button', { name: 'Abrir fatura' }).click()
  await expect(page.getByText('Soma confere com o total impresso na fatura.')).toBeVisible()
  const firstUrl = page.url()

  // A senha salva abre a fatura sem pop-up; a mesma fatura abre a importação existente.
  await readInvoice(page, cardName)
  await expect(page.getByText('Esta fatura já tinha sido importada.')).toBeVisible()
  await expect(page).toHaveURL(firstUrl)

  await page.getByRole('button', { name: /^Confirmar/ }).click()
  await expect(page.getByText('Lançamentos criados.')).toBeVisible()
  expect((await cardTransactions(page, cardName)).length).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Desfazer importação' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Desfazer' }).click()
  await expect(page.getByText('Importação desfeita.')).toBeVisible()
  await expect(page).toHaveURL(/\/faturas$/)
  expect(await cardTransactions(page, cardName)).toHaveLength(0)

  await navigate(page, 'Cartões')
  await expect(page.getByText('Senha da fatura salva')).toBeVisible()
  await page.getByRole('button', { name: 'Esquecer senha' }).click()
  await expect(page.getByText('Senha esquecida.')).toBeVisible()
  await expect(page.getByText('Senha da fatura salva')).toHaveCount(0)
})
