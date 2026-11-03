import fs from 'node:fs'
import path from 'node:path'

import { expect, type Locator, test } from '@playwright/test'

import { login, monthParam, navigate } from '../e2e/helpers'
import { OUTPUT, seedDemo } from './seed'

test.use({
  viewport: { width: 1280, height: 720 },
  video: { mode: 'on', size: { width: 1280, height: 720 } },
  colorScheme: 'light',
})

interface Chapter {
  at: number
  pt: string
  en: string
}

/** As opções de categoria levam o emoji na frente ("🛒 Mercado"): escolhe pelo nome. */
async function chooseCategory(select: Locator, name: string) {
  const value = await select.locator('option', { hasText: name }).first().getAttribute('value')
  await select.selectOption(value ?? '')
}

test('tour pelo MoneyLens com dados inventados', async ({ page }) => {
  const start = Date.now()
  await login(page)

  // Proteção: só roda no servidor temporário do E2E, ainda vazio (nunca num banco com dados de verdade).
  const before = await (await page.request.get(`/api/transactions?month=${monthParam()}`)).json()
  expect(before).toEqual([])

  await seedDemo(page.request, new Date())
  await page.reload()

  const chapters: Chapter[] = []
  const stop = async (pt: string, en: string, ms: number) => {
    chapters.push({ at: Math.round((Date.now() - start) / 100) / 10, pt, en })
    await page.waitForTimeout(ms)
  }

  await expect(page.getByText('Gasto até agora')).toBeVisible()
  await stop(
    'Painel: receitas, gastos, orçamento 50/30/20 e a previsão do mês.',
    'Dashboard: income, spending, the 50/30/20 budget and the monthly forecast.',
    6000,
  )
  await page.mouse.wheel(0, 700)
  await stop('Para onde foi o dinheiro e as faturas dos cartões.', 'Where the money went and the card bills.', 5000)

  await navigate(page, 'Lançamentos')
  await stop(
    'Lançamentos do mês, com parcelas e fixas.',
    'Monthly transactions, with installments and recurring bills.',
    4000,
  )
  await page.getByRole('button', { name: 'Mês anterior' }).click()
  await stop('Cada mês fica guardado para comparar.', 'Every month is kept for comparison.', 5000)
  await page.getByRole('button', { name: 'Novo lançamento' }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await stop(
    'Lançar leva segundos: valor, categoria, forma de pagamento e parcelas.',
    'Adding one takes seconds: amount, category, payment method and installments.',
    5000,
  )
  await page.keyboard.press('Escape')

  await navigate(page, 'Fixas')
  await stop(
    'Fixas: salário e contas que se repetem, confirmadas com um clique.',
    'Recurring: salary and bills that repeat, confirmed with one click.',
    5000,
  )

  await navigate(page, 'Cartões')
  await page.getByRole('button', { name: 'Ver faturas' }).first().click()
  await stop(
    'Cada fatura com a situação e o limite usado.',
    'Each card bill with its status and the limit in use.',
    5000,
  )
  await page.keyboard.press('Escape')

  await navigate(page, 'Importar')
  await stop(
    'Faturas e extratos em PDF: o arquivo é lido e descartado.',
    'PDF bills and statements: the file is read and then discarded.',
    4000,
  )
  await page.locator('a[href^="/faturas/"]').first().click()
  await expect(page.getByText('Soma confere com o total impresso na fatura.')).toBeVisible()
  await stop(
    'O app confere a soma com o total da fatura e sugere as categorias.',
    'The app checks the sum against the bill total and suggests categories.',
    6000,
  )
  await chooseCategory(page.getByLabel('Categoria de LOJA DESCONHECIDA'), 'Lazer')
  await page.getByRole('button', { name: 'Resolver' }).click()
  await expect(page.getByText('Nada em standby.')).toBeVisible()
  await stop(
    'O que ele não reconhece fica em standby até você decidir.',
    'Anything it does not recognize waits in standby for you to decide.',
    4000,
  )

  await navigate(page, 'Previsão')
  await stop(
    'Previsão do mês por categoria, com um modelo treinado em PyTorch.',
    'Monthly forecast per category, from a model trained with PyTorch.',
    6000,
  )
  await page.mouse.wheel(0, 600)
  await stop(
    'Para cada categoria: o valor provável e o máximo provável.',
    'For each category: the likely amount and the likely maximum.',
    4000,
  )

  await navigate(page, 'Tetos')
  const bell = page.locator('aside').getByRole('button', { name: 'Alertas de teto' })
  await expect(bell).toContainText(/\d/)
  await stop(
    'Tetos de gasto por valor ou por % da renda, com alertas antes de estourar.',
    'Spending limits by amount or % of income, with alerts before they are exceeded.',
    5000,
  )
  await page.getByRole('button', { name: 'Novo teto' }).first().click()
  await chooseCategory(page.getByLabel('Categoria'), 'Mercado')
  await page.getByRole('button', { name: 'Usar sugestão' }).click()
  await stop(
    'O app sugere um teto a partir do histórico; a decisão é sua.',
    'The app suggests a limit from your history; the decision is yours.',
    6000,
  )
  await page.getByRole('button', { name: 'Cancelar' }).click()
  await bell.click()
  await stop('Os alertas ficam no sino.', 'Alerts live behind the bell.', 4000)
  await page.keyboard.press('Escape')

  await navigate(page, 'Balanço anual')
  await stop('Balanço anual: o ano inteiro, mês a mês.', 'Yearly overview: the whole year, month by month.', 5000)

  fs.mkdirSync(OUTPUT, { recursive: true })
  fs.writeFileSync(path.join(OUTPUT, 'chapters.json'), JSON.stringify(chapters, null, 2))
  await page.close()
  await page.video()?.saveAs(path.join(OUTPUT, 'tour.webm'))
})
