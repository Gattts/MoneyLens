import { render, screen } from '@testing-library/react'
import userEvent, { PointerEventsCheckLevel } from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { FormDialog } from './FormDialog'

describe('FormDialog', () => {
  it('não fecha (nem perde o que foi digitado) com um clique fora da janela', async () => {
    const onOpenChange = vi.fn()
    render(
      <FormDialog open onOpenChange={onOpenChange} title="Novo lançamento">
        <input aria-label="Descrição" defaultValue="Conta de luz" />
      </FormDialog>,
    )
    // O modal deixa o fundo com pointer-events: none; o clique fora precisa ignorar essa checagem.
    await userEvent.setup({ pointerEventsCheck: PointerEventsCheckLevel.Never }).click(document.body)
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    expect(screen.getByLabelText('Descrição')).toHaveValue('Conta de luz')
  })

  it('fecha pelo botão de fechar', async () => {
    const onOpenChange = vi.fn()
    render(
      <FormDialog open onOpenChange={onOpenChange} title="Novo lançamento">
        <p>conteúdo</p>
      </FormDialog>,
    )
    await userEvent.click(screen.getByRole('button', { name: /close|fechar/i }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('com algo digitado, Esc pergunta antes de descartar', async () => {
    const onOpenChange = vi.fn()
    render(
      <FormDialog open onOpenChange={onOpenChange} title="Novo lançamento">
        <input aria-label="Descrição" />
      </FormDialog>,
    )
    await userEvent.type(screen.getByLabelText('Descrição'), 'Conta de luz')
    await userEvent.keyboard('{Escape}')
    expect(await screen.findByText('Descartar o que foi digitado?')).toBeInTheDocument()
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
    await userEvent.click(screen.getByRole('button', { name: 'Continuar editando' }))
    expect(screen.getByLabelText('Descrição')).toHaveValue('Conta de luz')
    await userEvent.keyboard('{Escape}')
    await userEvent.click(await screen.findByRole('button', { name: 'Descartar' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('sem nada digitado, Esc fecha direto', async () => {
    const onOpenChange = vi.fn()
    render(
      <FormDialog open onOpenChange={onOpenChange} title="Novo lançamento">
        <input aria-label="Descrição" />
      </FormDialog>,
    )
    await userEvent.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
