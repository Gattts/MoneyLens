import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import type { Card, Invoice } from '@/lib/types'

import { InvoiceDialog } from './InvoiceDialog'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: {
      ...original.api,
      cards: { ...original.api.cards, invoice: vi.fn(), pay: vi.fn() },
      cardPayments: { remove: vi.fn() },
    },
  }
})

const CARD = {
  id: 7,
  name: 'Inter',
  current_invoice: { month: '2026-10' },
} as Card

function invoice(overrides: Partial<Invoice>): Invoice {
  return {
    card_id: 7,
    month: '2026-10',
    closing_date: '2026-10-20',
    due_date: '2026-10-30',
    period_start: '2026-09-20',
    period_end: '2026-10-19',
    total_cents: 12_345,
    status: 'closed',
    paid_cents: 0,
    remaining_cents: 12_345,
    paid_on: null,
    transactions: [],
    payments: [],
    ...overrides,
  }
}

function renderDialog() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <InvoiceDialog card={CARD} onClose={vi.fn()} />
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

describe('InvoiceDialog, pagamentos', () => {
  beforeEach(() => {
    vi.mocked(api.cards.invoice).mockReset()
    vi.mocked(api.cards.pay)
      .mockReset()
      .mockResolvedValue(invoice({ status: 'paid', remaining_cents: 0 }))
    vi.mocked(api.cardPayments.remove).mockReset().mockResolvedValue(undefined)
  })

  it('fatura fechada: marcar como paga com hoje e o que falta', async () => {
    vi.mocked(api.cards.invoice).mockResolvedValue(invoice({}))
    const user = renderDialog()
    await user.click(await screen.findByRole('button', { name: 'Marcar como paga' }))
    expect(screen.getByLabelText('Data do pagamento')).toHaveValue(todayIso())
    expect(screen.getByLabelText('Valor pago')).toHaveValue('123,45')
    await user.click(screen.getByRole('button', { name: 'Salvar pagamento' }))
    expect(api.cards.pay).toHaveBeenCalledWith(7, {
      invoice_month: '2026-10',
      paid_on: todayIso(),
      amount_cents: 12_345,
    })
  })

  it('lista os pagamentos com a origem e só deixa excluir os feitos à mão ou pelo extrato', async () => {
    vi.mocked(api.cards.invoice).mockResolvedValue(
      invoice({
        status: 'paid',
        paid_on: '2026-10-28',
        remaining_cents: 0,
        payments: [
          { id: 1, paid_on: '2026-10-25', amount_cents: 2_345, source: 'manual' },
          { id: 2, paid_on: '2026-10-26', amount_cents: 5_000, source: 'account_statement' },
          { id: 3, paid_on: '2026-10-28', amount_cents: 5_000, source: 'card_invoice' },
        ],
      }),
    )
    const user = renderDialog()
    expect(await screen.findByText('Paga em 28/10')).toBeInTheDocument()
    expect(screen.getByText(/à mão/)).toBeInTheDocument()
    expect(screen.getByText(/do extrato/)).toBeInTheDocument()
    expect(screen.getByText(/da fatura seguinte/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Excluir pagamento/ })).toHaveLength(2)
    expect(screen.queryByRole('button', { name: 'Marcar como paga' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Excluir pagamento de 25/10/2026' }))
    expect(api.cardPayments.remove).toHaveBeenCalledWith(1)
  })

  it.each(['open', 'paid_before_tracking'] as const)('fatura %s não oferece marcar como paga', async (status) => {
    vi.mocked(api.cards.invoice).mockResolvedValue(invoice({ status }))
    renderDialog()
    expect(await screen.findByText('Total')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Marcar como paga' })).not.toBeInTheDocument()
  })
})
