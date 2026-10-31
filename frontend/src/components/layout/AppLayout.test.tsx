import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext } from '@/features/auth/auth-context'
import { api } from '@/lib/api'

import { AppLayout } from './AppLayout'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return { ...original, api: { ...original.api, alerts: { list: vi.fn(), read: vi.fn() } } }
})
vi.mocked(api.alerts.list).mockResolvedValue({ unread: 0, items: [] })

function renderLayout(isAdmin: boolean, path = '/') {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <AuthContext.Provider value={{ user: { username: 'ana', is_admin: isAdmin }, logout: vi.fn() }}>
          <AppLayout />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('AppLayout', () => {
  it('o menu só mostra Usuários para administradores', () => {
    renderLayout(false)
    expect(screen.queryByRole('link', { name: 'Usuários' })).not.toBeInTheDocument()
  })

  it('o sino dos alertas fica no menu lateral e no cabeçalho do celular', () => {
    renderLayout(false)
    expect(screen.getAllByRole('button', { name: 'Alertas de teto' })).toHaveLength(2)
    expect(screen.getAllByRole('link', { name: 'Tetos' }).length).toBeGreaterThan(0)
  })

  it('o conteúdo informa a rota que está na tela (os testes de ponta a ponta esperam por ela)', () => {
    renderLayout(false, '/lancamentos?mes=2026-10')
    expect(screen.getByRole('main')).toHaveAttribute('data-route', '/lancamentos')
  })

  it('administrador vê Usuários no menu', () => {
    renderLayout(true)
    expect(screen.getAllByRole('link', { name: 'Usuários' }).length).toBeGreaterThan(0)
  })
})
