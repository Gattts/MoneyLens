import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/api'

import { LoginPage } from './LoginPage'

function renderLogin(onLogin: (username: string, password: string) => Promise<unknown>) {
  render(
    <MemoryRouter>
      <LoginPage onLogin={onLogin} />
    </MemoryRouter>,
  )
}

describe('LoginPage', () => {
  it('pede usuário e senha antes de chamar o servidor', async () => {
    const onLogin = vi.fn()
    renderLogin(onLogin)
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByText('Informe o usuário.')).toBeInTheDocument()
    expect(screen.getByText('Informe a senha.')).toBeInTheDocument()
    expect(onLogin).not.toHaveBeenCalled()
  })

  it('mostra a mensagem do servidor quando a senha está errada', async () => {
    const onLogin = vi.fn().mockRejectedValue(new ApiError(401, 'Usuário ou senha incorretos.'))
    renderLogin(onLogin)
    await userEvent.type(screen.getByLabelText('Usuário'), 'ana')
    await userEvent.type(screen.getByLabelText('Senha'), 'errada')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuário ou senha incorretos.')
    expect(onLogin).toHaveBeenCalledWith('ana', 'errada')
  })

  it('envia uma vez só com clique duplo', async () => {
    const onLogin = vi.fn(() => new Promise<void>(() => {}))
    renderLogin(onLogin)
    await userEvent.type(screen.getByLabelText('Usuário'), 'ana')
    await userEvent.type(screen.getByLabelText('Senha'), 'senha-segura')
    await userEvent.dblClick(screen.getByRole('button', { name: 'Entrar' }))
    expect(onLogin).toHaveBeenCalledTimes(1)
  })

  it('mostra a marca MoneyLens', () => {
    renderLogin(vi.fn())
    expect(screen.getByText('MoneyLens')).toBeInTheDocument()
    expect(screen.queryByText('Financeiro')).not.toBeInTheDocument()
  })

  it('tem o link Primeiro acesso', () => {
    renderLogin(vi.fn())
    expect(screen.getByRole('link', { name: 'Primeiro acesso' })).toHaveAttribute('href', '/primeiro-acesso')
  })
})
