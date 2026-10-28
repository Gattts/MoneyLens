import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { BudgetSettingsForm } from './BudgetSettingsForm'

const initial = { needs_pct: 50, wants_pct: 30, savings_pct: 20 }

async function retype(label: string, value: string) {
  const input = screen.getByLabelText(label)
  await userEvent.clear(input)
  if (value) await userEvent.type(input, value)
}

describe('BudgetSettingsForm', () => {
  it('mostra quanto falta ou passa de 100% enquanto a pessoa digita', async () => {
    render(<BudgetSettingsForm initial={initial} onSubmit={vi.fn()} />)
    expect(screen.getByText('Tudo certo: 100%')).toBeInTheDocument()
    await retype('Necessidades (%)', '60')
    expect(screen.getByText('Passou 10%')).toBeInTheDocument()
    await retype('Necessidades (%)', '40')
    expect(screen.getByText('Faltam 10%')).toBeInTheDocument()
  })

  it('não salva se a soma não fecha 100%', async () => {
    const onSubmit = vi.fn()
    render(<BudgetSettingsForm initial={initial} onSubmit={onSubmit} />)
    await retype('Poupança (%)', '30')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Os percentuais precisam somar 100%.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('recusa campo vazio e salva a nova divisão', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<BudgetSettingsForm initial={initial} onSubmit={onSubmit} />)
    await retype('Desejos (%)', '')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Use um número inteiro de 0 a 100.')).toBeInTheDocument()
    await retype('Desejos (%)', '20')
    await retype('Poupança (%)', '30')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith({ needs_pct: 50, wants_pct: 20, savings_pct: 30 })
  })
})
