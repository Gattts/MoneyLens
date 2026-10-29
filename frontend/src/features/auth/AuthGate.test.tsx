import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useContext } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'

import { AuthContext } from './auth-context'
import { AuthGate } from './AuthGate'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: { ...original.api, auth: { me: vi.fn(), login: vi.fn(), logout: vi.fn() } },
  }
})

function LogoutButton() {
  const auth = useContext(AuthContext)
  return <button onClick={() => void auth?.logout()}>Sair</button>
}

describe('AuthGate', () => {
  it('sair volta para a tela de login sem recarregar a página', async () => {
    vi.mocked(api.auth.me).mockResolvedValue({ username: 'ana', is_admin: false })
    vi.mocked(api.auth.logout).mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(
      <MemoryRouter>
        <QueryClientProvider client={new QueryClient()}>
          <AuthGate>
            <LogoutButton />
          </AuthGate>
        </QueryClientProvider>
      </MemoryRouter>,
    )
    await user.click(await screen.findByRole('button', { name: 'Sair' }))
    expect(await screen.findByLabelText('Usuário')).toBeInTheDocument()
    expect(api.auth.logout).toHaveBeenCalledTimes(1)
  })
})
