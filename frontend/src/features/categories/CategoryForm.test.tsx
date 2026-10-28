import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CategoryForm } from './CategoryForm'

describe('CategoryForm', () => {
  it('categoria de despesa exige o grupo do orçamento', async () => {
    const onSubmit = vi.fn()
    render(<CategoryForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    await userEvent.type(screen.getByLabelText('Nome'), 'Pets')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Escolha o grupo do orçamento.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('categoria de receita não tem grupo e é enviada sem ele', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    render(<CategoryForm onSubmit={onSubmit} onCancel={vi.fn()} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Receita' }))
    expect(screen.queryByLabelText('Grupo do orçamento')).not.toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Nome'), 'Freela')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Freela', kind: 'income', default_bucket: null }),
    )
  })
})
