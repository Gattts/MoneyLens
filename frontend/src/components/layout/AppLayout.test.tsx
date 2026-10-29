import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext } from '@/features/auth/auth-context'

import { AppLayout } from './AppLayout'

function renderLayout(isAdmin: boolean) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
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

  it('administrador vê Usuários no menu', () => {
    renderLayout(true)
    expect(screen.getAllByRole('link', { name: 'Usuários' }).length).toBeGreaterThan(0)
  })
})
