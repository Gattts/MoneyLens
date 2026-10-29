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
  // Espera a tela trocar: senão o preenchimento cai nos campos da tela de login.
  await expect(page.getByRole('button', { name: 'Ativar conta' })).toBeVisible()
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

test('código errado no primeiro acesso avisa o motivo e não fala em sessão expirada', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  await expect(page.getByText('Sua sessão expirou')).toHaveCount(0) // primeira abertura, sem sessão
  await page.getByRole('link', { name: 'Primeiro acesso' }).click()
  // Espera a tela trocar: senão o preenchimento cai nos campos da tela de login.
  await expect(page.getByRole('button', { name: 'Ativar conta' })).toBeVisible()
  await page.getByLabel('Usuário').fill('ninguem')
  await page.getByLabel('Código de convite').fill('AAAA-AAAA')
  await page.getByLabel('Nova senha').fill('senha-boa-123')
  await page.getByLabel('Repita a senha').fill('senha-boa-123')
  await page.getByRole('button', { name: 'Ativar conta' }).click()
  await expect(page.getByText('Usuário ou código inválido, ou o convite expirou.')).toBeVisible()
  await page.getByRole('link', { name: 'Voltar ao login' }).click()
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  await expect(page.getByText('Sua sessão expirou')).toHaveCount(0)
})
