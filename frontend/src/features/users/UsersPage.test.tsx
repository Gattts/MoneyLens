import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthContext } from '@/features/auth/auth-context'
import { api } from '@/lib/api'
import type { AdminUser } from '@/lib/types'

import { UsersPage } from './UsersPage'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: { ...original.api, admin: { users: { list: vi.fn(), create: vi.fn(), invite: vi.fn(), remove: vi.fn() } } },
  }
})

const users = vi.mocked(api.admin.users)
const ANA: AdminUser = { id: 1, username: 'ana', is_admin: true, status: 'active', invite_expires_at: null }
const JOANA: AdminUser = { id: 2, username: 'joana', is_admin: false, status: 'active', invite_expires_at: null }
const MARIA: AdminUser = {
  id: 3,
  username: 'maria',
  is_admin: false,
  status: 'pending',
  invite_expires_at: '2026-11-04T12:00:00Z',
}

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthContext.Provider value={{ user: { username: 'ana', is_admin: true }, logout: vi.fn() }}>
        <UsersPage />
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

describe('UsersPage', () => {
  beforeEach(() => {
    users.list.mockReset().mockResolvedValue([ANA, JOANA, MARIA])
    users.create.mockReset().mockResolvedValue({ user: MARIA, code: 'K7QH-3MPW' })
  })

  it('criar usuário mostra o código e o texto pronto para enviar', async () => {
    const user = renderPage()
    await user.click(await screen.findByRole('button', { name: 'Novo usuário' }))
    await user.type(screen.getByLabelText('Nome de usuário'), 'maria')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(users.create).toHaveBeenCalledWith({ username: 'maria' })
    expect(await screen.findByText('K7QH-3MPW')).toBeInTheDocument()
    expect(
      screen.getByText(/clique em "Primeiro acesso" e use o usuário maria e o código K7QH-3MPW/),
    ).toBeInTheDocument()
  })

  it('copiar coloca o texto na área de transferência', async () => {
    const user = renderPage() // o user-event instala uma área de transferência própria, lida abaixo
    await user.click(await screen.findByRole('button', { name: 'Novo usuário' }))
    await user.type(screen.getByLabelText('Nome de usuário'), 'maria')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    await user.click(await screen.findByRole('button', { name: 'Copiar' }))
    expect(await navigator.clipboard.readText()).toContain('o código K7QH-3MPW')
  })

  it('não mostra Gerar novo convite para si mesmo nem Excluir para ativos', async () => {
    renderPage()
    const anaRow = await screen.findByRole('listitem', { name: 'ana' })
    expect(within(anaRow).queryByRole('button', { name: /Gerar novo convite/ })).not.toBeInTheDocument()
    expect(within(anaRow).getByText('Administrador')).toBeInTheDocument()
    const joanaRow = screen.getByRole('listitem', { name: 'joana' })
    expect(within(joanaRow).getByRole('button', { name: /Gerar novo convite/ })).toBeInTheDocument()
    expect(within(joanaRow).queryByRole('button', { name: /Excluir/ })).not.toBeInTheDocument()
    const mariaRow = screen.getByRole('listitem', { name: 'maria' })
    expect(within(mariaRow).getByText(/Aguardando primeiro acesso \(convite vale até 04\/11\)/)).toBeInTheDocument()
    expect(within(mariaRow).getByRole('button', { name: /Excluir/ })).toBeInTheDocument()
  })
})
