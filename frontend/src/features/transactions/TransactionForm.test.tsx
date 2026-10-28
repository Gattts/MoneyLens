import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/lib/api'
import type { Card, Category, Goal, Transaction } from '@/lib/types'

import { TransactionForm } from './TransactionForm'

const categories: Category[] = [
  { id: 1, name: 'Mercado', icon: '🛒', description: '', kind: 'expense', default_bucket: 'needs', archived: false },
  { id: 2, name: 'Salário', icon: '💸', description: '', kind: 'income', default_bucket: null, archived: false },
  {
    id: 3,
    name: 'Investimentos',
    icon: '📈',
    description: '',
    kind: 'expense',
    default_bucket: 'savings',
    archived: false,
  },
  { id: 4, name: 'Antiga', icon: '📦', description: '', kind: 'expense', default_bucket: 'wants', archived: true },
]
const cards = [{ id: 7, name: 'Nubank', archived: false }] as Card[]
const goals = [{ id: 9, name: 'Reserva', icon: '🛟', archived: false }] as Goal[]

function setup(props: Partial<React.ComponentProps<typeof TransactionForm>> = {}) {
  const onSubmit = props.onSubmit ?? vi.fn().mockResolvedValue(undefined)
  render(
    <TransactionForm
      categories={categories}
      cards={cards}
      goals={goals}
      defaultDate="2026-10-27"
      onSubmit={onSubmit}
      onCancel={vi.fn()}
      {...props}
    />,
  )
  return { user: userEvent.setup(), onSubmit }
}

describe('TransactionForm', () => {
  it('mostra os erros em português e não envia com campos obrigatórios vazios', async () => {
    const { user, onSubmit } = setup()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Informe a descrição.')).toBeInTheDocument()
    expect(screen.getByText('Informe o valor.')).toBeInTheDocument()
    expect(screen.getByText('Escolha a categoria.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it.each([
    ['abc', 'Valor inválido. Exemplo: 1.234,56'],
    ['-10', 'Valor inválido. Exemplo: 1.234,56'],
    ['0', 'Informe um valor maior que zero.'],
    ['2.000.000.000', 'O valor máximo é R$ 1.000.000.000,00.'],
  ])('recusa o valor %j', async (typed, message) => {
    const { user, onSubmit } = setup()
    await user.type(screen.getByLabelText('Valor'), typed)
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('envia o lançamento em centavos com o grupo da categoria', async () => {
    const { user, onSubmit } = setup()
    await user.type(screen.getByLabelText('Descrição'), '  Feira  ')
    await user.type(screen.getByLabelText('Valor'), '1.234,56')
    await user.selectOptions(screen.getByLabelText('Categoria'), '1')
    expect(screen.getByLabelText('Grupo do orçamento')).toHaveValue('needs')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith({
      description: 'Feira',
      kind: 'expense',
      amount_cents: 123456,
      date: '2026-10-27',
      category_id: 1,
      bucket: 'needs',
      payment_method: 'pix',
      card_id: null,
      goal_id: null,
      notes: '',
      installments: 1,
    })
  })

  it('pede o cartão e mostra a divisão das parcelas no crédito', async () => {
    const { user, onSubmit } = setup()
    expect(screen.queryByLabelText('Cartão')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Descrição'), 'Notebook')
    await user.type(screen.getByLabelText('Valor'), '100,00')
    await user.selectOptions(screen.getByLabelText('Categoria'), '1')
    await user.selectOptions(screen.getByLabelText('Forma de pagamento'), 'credit_card')
    await user.clear(screen.getByLabelText('Parcelas'))
    await user.type(screen.getByLabelText('Parcelas'), '3')
    expect(screen.getByText('3× de R$ 33,33 (a primeira de R$ 33,34)')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Escolha o cartão.')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Cartão'), '7')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ payment_method: 'credit_card', card_id: 7, installments: 3, amount_cents: 10000 }),
    )
  })

  it('recusa número de parcelas fora de 1 a 48', async () => {
    const { user } = setup()
    await user.selectOptions(screen.getByLabelText('Forma de pagamento'), 'credit_card')
    await user.clear(screen.getByLabelText('Parcelas'))
    await user.type(screen.getByLabelText('Parcelas'), '60')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Use de 1 a 48 parcelas.')).toBeInTheDocument()
  })

  it('receita esconde o grupo do orçamento e lista só categorias de receita', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('radio', { name: 'Receita' }))
    expect(screen.queryByLabelText('Grupo do orçamento')).not.toBeInTheDocument()
    const options = Array.from(screen.getByLabelText('Categoria').querySelectorAll('option')).map((o) => o.textContent)
    expect(options).toContain('💸 Salário')
    expect(options).not.toContain('🛒 Mercado')
  })

  it('não oferece categoria arquivada', () => {
    setup()
    const options = Array.from(screen.getByLabelText('Categoria').querySelectorAll('option')).map((o) => o.textContent)
    expect(options).not.toContain('📦 Antiga')
  })

  it('só oferece meta para lançamentos de poupança', async () => {
    const { user } = setup()
    expect(screen.queryByLabelText('Meta')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Categoria'), '3')
    expect(screen.getByLabelText('Meta')).toBeInTheDocument()
  })

  it('envia uma vez só mesmo com clique duplo', async () => {
    const onSubmit = vi.fn(() => new Promise<void>(() => {}))
    const { user } = setup({ onSubmit })
    await user.type(screen.getByLabelText('Descrição'), 'Feira')
    await user.type(screen.getByLabelText('Valor'), '10')
    await user.selectOptions(screen.getByLabelText('Categoria'), '1')
    await user.dblClick(screen.getByRole('button', { name: 'Salvar' }))
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Salvando/ })).toBeDisabled()
  })

  it('mostra o erro do servidor no campo certo e o erro geral no topo', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiError(422, 'Verifique os campos informados.', { date: 'Use uma data entre 01/01/2000 e 31/12/2100.' }),
      )
      .mockRejectedValueOnce(new ApiError(0, 'Não foi possível falar com o servidor.'))
    const { user } = setup({ onSubmit })
    await user.type(screen.getByLabelText('Descrição'), 'Feira')
    await user.type(screen.getByLabelText('Valor'), '10')
    await user.selectOptions(screen.getByLabelText('Categoria'), '1')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Use uma data entre 01/01/2000 e 31/12/2100.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Não foi possível falar com o servidor.')).toBeInTheDocument()
  })

  it('na edição preenche os campos e não oferece parcelamento', () => {
    const initial = {
      id: 5,
      description: 'Aluguel',
      kind: 'expense',
      amount_cents: 123456,
      date: '2026-10-10',
      category_id: 1,
      bucket: 'needs',
      payment_method: 'credit_card',
      card_id: 7,
      goal_id: null,
      notes: 'outubro',
    } as Transaction
    setup({ initial })
    expect(screen.getByLabelText('Descrição')).toHaveValue('Aluguel')
    expect(screen.getByLabelText('Valor')).toHaveValue('1.234,56')
    expect(screen.getByLabelText('Data')).toHaveValue('2026-10-10')
    expect(screen.queryByLabelText('Parcelas')).not.toBeInTheDocument()
  })

  it('sem cartão ativo, explica onde cadastrar um', async () => {
    const { user } = setup({ cards: [{ id: 7, name: 'Antigo', archived: true }] as Card[] })
    await user.selectOptions(screen.getByLabelText('Forma de pagamento'), 'credit_card')
    expect(screen.getByText('Nenhum cartão ativo. Cadastre um na página Cartões.')).toBeInTheDocument()
  })

  it('sem categoria ativa do tipo escolhido, explica onde criar uma', async () => {
    const { user } = setup({ categories: categories.filter((c) => c.kind === 'expense') })
    await user.click(screen.getByRole('radio', { name: 'Receita' }))
    expect(screen.getByText('Nenhuma categoria de receita ativa. Crie uma na página Categorias.')).toBeInTheDocument()
  })
})
