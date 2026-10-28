import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CardForm } from './CardForm'

describe('CardForm', () => {
  it('valida dias do mês e limite', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<CardForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText('Nome do cartão'), 'Nubank')
    await user.type(screen.getByLabelText('Limite'), 'muito')
    await user.type(screen.getByLabelText('Dia do fechamento'), '0')
    await user.type(screen.getByLabelText('Dia do vencimento'), '40')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Valor inválido. Exemplo: 1.234,56')).toBeInTheDocument()
    expect(screen.getAllByText('Use um dia de 1 a 31.')).toHaveLength(2)
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('aceita limite zero e envia em centavos', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<CardForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText('Nome do cartão'), 'Nubank')
    await user.type(screen.getByLabelText('Limite'), '0')
    await user.type(screen.getByLabelText('Dia do fechamento'), '29')
    await user.type(screen.getByLabelText('Dia do vencimento'), '7')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Nubank',
      limit_cents: 0,
      closing_day: 29,
      due_day: 7,
      archived: false,
    })
  })
})
