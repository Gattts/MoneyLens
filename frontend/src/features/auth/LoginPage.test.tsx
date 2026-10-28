import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/api'

import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  it('pede usuário e senha antes de chamar o servidor', async () => {
    const onLogin = vi.fn()
    render(<LoginPage onLogin={onLogin} />)
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByText('Informe o usuário.')).toBeInTheDocument()
    expect(screen.getByText('Informe a senha.')).toBeInTheDocument()
    expect(onLogin).not.toHaveBeenCalled()
  })

  it('mostra a mensagem do servidor quando a senha está errada', async () => {
    const onLogin = vi.fn().mockRejectedValue(new ApiError(401, 'Usuário ou senha incorretos.'))
    render(<LoginPage onLogin={onLogin} />)
    await userEvent.type(screen.getByLabelText('Usuário'), 'ana')
    await userEvent.type(screen.getByLabelText('Senha'), 'errada')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Usuário ou senha incorretos.')
    expect(onLogin).toHaveBeenCalledWith('ana', 'errada')
  })

  it('envia uma vez só com clique duplo', async () => {
    const onLogin = vi.fn(() => new Promise<void>(() => {}))
    render(<LoginPage onLogin={onLogin} />)
    await userEvent.type(screen.getByLabelText('Usuário'), 'ana')
    await userEvent.type(screen.getByLabelText('Senha'), 'senha-segura')
    await userEvent.dblClick(screen.getByRole('button', { name: 'Entrar' }))
    expect(onLogin).toHaveBeenCalledTimes(1)
  })
})
