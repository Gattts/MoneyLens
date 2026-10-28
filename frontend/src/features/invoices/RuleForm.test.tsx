import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/api'

import { RuleForm } from './RuleForm'
import { category } from './test-data'

const CATEGORIES = [category({ id: 10, name: 'Lazer' }), category({ id: 12, name: 'Salário', kind: 'income' })]

describe('RuleForm', () => {
  it('exige texto com 2 ou mais caracteres e categoria', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<RuleForm categories={CATEGORIES} onSubmit={onSubmit} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText('Texto'), 'a')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Use pelo menos 2 caracteres.')).toBeInTheDocument()
    expect(screen.getByText('Escolha a categoria.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('envia o texto, a comparação e a categoria', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<RuleForm categories={CATEGORIES} onSubmit={onSubmit} onCancel={vi.fn()} />)
    expect(screen.queryByRole('option', { name: /Salário/ })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Texto'), 'padaria')
    await user.click(screen.getByLabelText('Exata'))
    await user.selectOptions(screen.getByLabelText('Categoria'), '10')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith({ pattern: 'padaria', match_type: 'exact', category_id: 10 })
  })

  it('mostra o erro do servidor "Já existe uma regra igual."', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(409, 'Já existe uma regra igual.'))
    render(<RuleForm categories={CATEGORIES} onSubmit={onSubmit} onCancel={vi.fn()} />)
    await user.type(screen.getByLabelText('Texto'), 'uber')
    await user.selectOptions(screen.getByLabelText('Categoria'), '10')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Já existe uma regra igual.')).toBeInTheDocument()
  })
})
