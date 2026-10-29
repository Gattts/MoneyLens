import { expect, test } from '@playwright/test'

import { createCard, login, navigate, unique } from './helpers'

const CODE = /^[A-HJKMNP-Z2-9]{4}-[A-HJKMNP-Z2-9]{4}$/

test('admin convida, a pessoa ativa a conta e vê só os próprios dados', async ({ page }) => {
  await login(page)
  const adminCard = unique('Cartão do admin')
  await createCard(page, adminCard)

  const username = `maria${Math.random().toString(36).slice(2, 7)}`
  await navigate(page, 'Usuários')
  await page.getByRole('button', { name: 'Novo usuário' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Nome de usuário').fill(username)
  await dialog.getByRole('button', { name: 'Salvar' }).click()
  const code = (await page.getByText(CODE).textContent())?.trim() ?? ''
  expect(code).toMatch(CODE)

  await page.getByRole('button', { name: 'Sair' }).click()
  await page.getByRole('link', { name: 'Primeiro acesso' }).click()
  await page.getByLabel('Usuário').fill(username)
  await page.getByLabel('Código de convite').fill(code.toLowerCase())
  await page.getByLabel('Nova senha').fill('senha-da-maria-123')
  await page.getByLabel('Repita a senha').fill('senha-da-maria-123')
  await page.getByRole('button', { name: 'Ativar conta' }).click()
  await expect(page.getByRole('heading', { name: 'Painel' })).toBeVisible()

  const menu = page.getByRole('navigation', { name: 'Principal' })
  await expect(menu.getByRole('link', { name: 'Usuários' })).toHaveCount(0)
  await navigate(page, 'Cartões')
  await expect(page.getByText(adminCard)).toHaveCount(0)
  await navigate(page, 'Categorias')
  await expect(page.getByText('Mercado').first()).toBeVisible()
})
