import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { Category } from '@/lib/types'

import { RecurringForm } from './RecurringForm'

const categories: Category[] = [
  { id: 1, name: 'Moradia', icon: '🏠', description: '', kind: 'expense', default_bucket: 'needs', archived: false },
]

async function fillValidRule(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Descrição'), 'Aluguel')
  await user.type(screen.getByLabelText('Valor'), '1.500,00')
  await user.selectOptions(screen.getByLabelText('Categoria'), '1')
  await user.clear(screen.getByLabelText('Dia do mês'))
  await user.type(screen.getByLabelText('Dia do mês'), '10')
}

describe('RecurringForm', () => {
  it('recusa dia fora do mês e mês final antes do inicial', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <RecurringForm
        categories={categories}
        cards={[]}
        defaultMonth="2026-10"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    )
    await fillValidRule(user)
    await user.clear(screen.getByLabelText('Dia do mês'))
    await user.type(screen.getByLabelText('Dia do mês'), '32')
    await user.type(screen.getByLabelText('Termina em (opcional)'), '2026-09')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Use um dia de 1 a 31.')).toBeInTheDocument()
    expect(screen.getByText('O mês final precisa ser igual ou posterior ao inicial.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('envia a fixa sem data de término', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(
      <RecurringForm
        categories={categories}
        cards={[]}
        defaultMonth="2026-10"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    )
    await fillValidRule(user)
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith({
      description: 'Aluguel',
      kind: 'expense',
      amount_cents: 150000,
      category_id: 1,
      bucket: 'needs',
      day_of_month: 10,
      payment_method: 'pix',
      card_id: null,
      start_month: '2026-10',
      end_month: null,
      notes: '',
    })
  })

  it('aceita o mês no formato brasileiro (MM/AAAA) e não descarta o mês final', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(
      <RecurringForm
        categories={categories}
        cards={[]}
        defaultMonth="2026-10"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    )
    await fillValidRule(user)
    await user.type(screen.getByLabelText('Termina em (opcional)'), '07/2027')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ start_month: '2026-10', end_month: '2027-07' }))
  })

  it('avisa quando o mês digitado está incompleto, em vez de salvar sem data final', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(
      <RecurringForm
        categories={categories}
        cards={[]}
        defaultMonth="2026-10"
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    )
    await fillValidRule(user)
    await user.type(screen.getByLabelText('Termina em (opcional)'), '13/2027')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Mês inválido. Use MM/AAAA, por exemplo 07/2027.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
