import os from 'node:os'
import path from 'node:path'

import { expect, type Page } from '@playwright/test'

export const USERNAME = 'teste'
export const PASSWORD = 'senha-de-teste-123'

export async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel('Usuário').fill(USERNAME)
  await page.getByLabel('Senha').fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { name: 'Painel' })).toBeVisible()
}

/** Clica num item do menu principal (outros links da página podem ter nomes parecidos). */
export async function navigate(page: Page, label: string) {
  const link = page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: label, exact: true })
  const target = new URL((await link.getAttribute('href')) ?? '/', 'http://app').pathname
  await link.click()
  // Espera a troca de rota (o link leva o mês na query): sem isso, um botão de mesmo nome na página anterior
  // (ex.: "Novo lançamento" no Painel) ainda pode receber o próximo clique.
  await expect.poll(() => new URL(page.url()).pathname).toBe(target)
}

/** Nome único por execução, para os testes não colidirem no mesmo banco. */
export function unique(prefix: string) {
  return `${prefix} ${Math.random().toString(36).slice(2, 7)}`
}

export function monthParam(offset = 0) {
  const now = new Date()
  const month = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  return `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}`
}

export async function createTransaction(page: Page, description: string, amount: string, category: string) {
  await page.getByRole('button', { name: 'Novo lançamento' }).first().click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Descrição').fill(description)
  await form.getByLabel('Valor').fill(amount)
  await form.getByLabel('Categoria').selectOption({ label: category })
  await form.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText('Lançamento salvo.').first()).toBeVisible()
}

/** Fatura sintética com senha, gerada pelo backend em e2e/global-setup.ts (nenhum dado real). */
export const INVOICE_PASSWORD = '1234'
export const INVOICE_PDF = path.join(os.tmpdir(), 'financeiro-e2e', 'fatura-sintetica.pdf')

export async function createCard(page: Page, name: string) {
  await navigate(page, 'Cartões')
  await page.getByRole('button', { name: 'Novo cartão' }).first().click()
  const form = page.getByRole('dialog')
  await form.getByLabel('Nome do cartão').fill(name)
  await form.getByLabel('Limite').fill('3.000,00')
  await form.getByLabel('Dia do fechamento').fill('5')
  await form.getByLabel('Dia do vencimento').fill('12')
  await form.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText('Cartão cadastrado.')).toBeVisible()
}
