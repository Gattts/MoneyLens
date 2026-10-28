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
  await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: label, exact: true }).click()
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
