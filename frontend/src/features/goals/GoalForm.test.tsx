import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { GoalForm } from './GoalForm'

describe('GoalForm', () => {
  it('exige nome e valor, com mensagens em português', async () => {
    const onSubmit = vi.fn()
    render(<GoalForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Informe o nome da meta.')).toBeInTheDocument()
    expect(screen.getByText('Informe o valor que quer juntar.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('envia em centavos, com a data-alvo opcional', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<GoalForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('Nome da meta'), 'Viagem')
    await userEvent.type(screen.getByLabelText('Valor a juntar'), '5.000')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Viagem',
      icon: '🎯',
      target_cents: 500000,
      target_date: null,
      archived: false,
    })
  })

  it('não descarta em silêncio uma data-alvo digitada pela metade', async () => {
    const onSubmit = vi.fn()
    render(<GoalForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('Nome da meta'), 'Viagem')
    await userEvent.type(screen.getByLabelText('Valor a juntar'), '5.000')
    // Com a data incompleta, o navegador devolve "" e marca validity.badInput.
    Object.defineProperty(screen.getByLabelText('Até quando (opcional)'), 'validity', { value: { badInput: true } })
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Data incompleta. Preencha dia, mês e ano ou apague o campo.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
