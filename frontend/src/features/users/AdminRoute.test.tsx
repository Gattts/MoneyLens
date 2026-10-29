import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext } from '@/features/auth/auth-context'

import { AdminRoute } from './AdminRoute'

function renderRoute(isAdmin: boolean) {
  render(
    <MemoryRouter>
      <AuthContext.Provider value={{ user: { username: 'bia', is_admin: isAdmin }, logout: vi.fn() }}>
        <AdminRoute>
          <p>Conteúdo de administração</p>
        </AdminRoute>
      </AuthContext.Provider>
    </MemoryRouter>,
  )
}

describe('AdminRoute', () => {
  it('quem não é administrador vê página não encontrada', () => {
    renderRoute(false)
    expect(screen.getByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
    expect(screen.queryByText('Conteúdo de administração')).not.toBeInTheDocument()
  })

  it('administrador vê o conteúdo', () => {
    renderRoute(true)
    expect(screen.getByText('Conteúdo de administração')).toBeInTheDocument()
  })
})
