import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/api'

import { FirstAccessPage } from './FirstAccessPage'

function renderPage(onActivate = vi.fn().mockResolvedValue(undefined)) {
  render(
    <MemoryRouter>
      <FirstAccessPage onActivate={onActivate} />
    </MemoryRouter>,
  )
  return { user: userEvent.setup(), onActivate }
}

async function fill(user: ReturnType<typeof userEvent.setup>, password = 'nova-senha-123', repeat = password) {
  await user.type(screen.getByLabelText('Usuário'), 'maria')
  await user.type(screen.getByLabelText('Código de convite'), 'k7qh-3mpw')
  await user.type(screen.getByLabelText('Nova senha'), password)
  await user.type(screen.getByLabelText('Repita a senha'), repeat)
}

describe('FirstAccessPage', () => {
  it('envia usuário, código e senha', async () => {
    const { user, onActivate } = renderPage()
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Ativar conta' }))
    expect(onActivate).toHaveBeenCalledWith({ username: 'maria', code: 'k7qh-3mpw', password: 'nova-senha-123' })
  })

  it('senhas diferentes não enviam', async () => {
    const { user, onActivate } = renderPage()
    await fill(user, 'nova-senha-123', 'outra-senha-123')
    await user.click(screen.getByRole('button', { name: 'Ativar conta' }))
    expect(await screen.findByText('As senhas não conferem.')).toBeInTheDocument()
    expect(onActivate).not.toHaveBeenCalled()
  })

  it('senha curta mostra a regra', async () => {
    const { user, onActivate } = renderPage()
    await fill(user, 'curta')
    await user.click(screen.getByRole('button', { name: 'Ativar conta' }))
    expect(await screen.findByText('Use de 8 a 128 caracteres.')).toBeInTheDocument()
    expect(onActivate).not.toHaveBeenCalled()
  })

  it('mostra a mensagem do servidor para código inválido', async () => {
    const refused = new ApiError(401, 'Usuário ou código inválido, ou o convite expirou.')
    const { user } = renderPage(vi.fn().mockRejectedValue(refused))
    await fill(user)
    await user.click(screen.getByRole('button', { name: 'Ativar conta' }))
    expect(await screen.findByText('Usuário ou código inválido, ou o convite expirou.')).toBeInTheDocument()
  })

  it('clique duplo em Ativar conta envia uma vez só', async () => {
    const { user, onActivate } = renderPage(vi.fn(() => new Promise(() => {})))
    await fill(user)
    await user.dblClick(screen.getByRole('button', { name: 'Ativar conta' }))
    expect(onActivate).toHaveBeenCalledTimes(1)
  })

  it('tem o link para voltar ao login', () => {
    renderPage()
    expect(screen.getByRole('link', { name: 'Voltar ao login' })).toHaveAttribute('href', '/')
  })
})
