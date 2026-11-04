import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Card, Category, Transaction } from '@/lib/types'

import { TransactionsTable } from './TransactionsTable'

const CATEGORY = {
  id: 1,
  name: 'Mercado',
  icon: '🛒',
  kind: 'expense',
  default_bucket: 'needs',
  archived: false,
} as Category
const CARD = { id: 7, name: 'Nubank', closing_day: 29, due_day: 5 } as Card

function row(overrides: Partial<Transaction>): Transaction {
  return {
    id: 1,
    description: 'Mercado do bairro',
    kind: 'expense',
    amount_cents: 10_000,
    date: '2026-11-10',
    category_id: 1,
    bucket: 'needs',
    payment_method: 'pix',
    card_id: null,
    goal_id: null,
    notes: '',
    installment_group: null,
    installment_number: null,
    installment_total: null,
    recurring_rule_id: null,
    recurrence_month: null,
    payment_month: '2026-11',
    ...overrides,
  }
}

function renderRows(rows: Transaction[]) {
  render(
    <TransactionsTable
      rows={rows}
      categories={[CATEGORY]}
      cards={[CARD]}
      goals={[]}
      onEdit={vi.fn()}
      onDelete={vi.fn()}
    />,
  )
}

describe('TransactionsTable, mês de pagamento', () => {
  it('compra no cartão paga em outro mês ganha a etiqueta "paga em"', () => {
    renderRows([
      row({ id: 1, description: 'No cartão', payment_method: 'credit_card', card_id: 7, payment_month: '2026-12' }),
      row({ id: 2, description: 'No Pix' }),
    ])
    const onCard = screen.getByText('No cartão').closest('tr')!
    expect(within(onCard).getByText('paga em dez/2026')).toBeInTheDocument()
    const onPix = screen.getByText('No Pix').closest('tr')!
    expect(within(onPix).queryByText(/paga em/)).not.toBeInTheDocument()
  })

  it('o rodapé soma as linhas listadas (pela data da compra), não o caixa do mês', () => {
    renderRows([row({})])
    expect(screen.getByText(/Despesas listadas/)).toBeInTheDocument()
  })
})
