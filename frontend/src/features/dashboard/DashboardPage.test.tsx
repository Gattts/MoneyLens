import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import type { Card, Invoice, MonthSummary } from '@/lib/types'

import { DashboardPage } from './DashboardPage'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: {
      ...original.api,
      summary: { ...original.api.summary, month: vi.fn() },
      cards: { ...original.api.cards, list: vi.fn(), invoice: vi.fn() },
      invoices: { ...original.api.invoices, list: vi.fn() },
    },
  }
})

const FLOW = { realized_cents: 0, pending_cents: 0, total_cents: 0 }
const SUMMARY: MonthSummary = {
  month: '2026-08',
  income: FLOW,
  needs: FLOW,
  wants: FLOW,
  savings: FLOW,
  balance_cents: 0,
  realized_balance_cents: 0,
  budget: [],
  thermometer: { status: 'no_data', spending_pct: null, limit_pct: 80 },
  by_category: [],
  pending: [],
}
const CARD: Card = {
  id: 7,
  name: 'Roxinho',
  limit_cents: 500_000,
  closing_day: 5,
  due_day: 12,
  archived: false,
  has_invoice_password: false,
  used_cents: 120_000,
  available_cents: 380_000,
  current_invoice: {
    month: '2026-10',
    closing_date: '2026-10-05',
    due_date: '2026-10-12',
    total_cents: 99_900,
    status: 'open',
  },
}
const AUGUST: Invoice = {
  card_id: 7,
  month: '2026-08',
  closing_date: '2026-08-05',
  due_date: '2026-08-12',
  period_start: '2026-07-05',
  period_end: '2026-08-04',
  total_cents: 45_678,
  status: 'past',
  transactions: [],
}

function renderAt(path: string) {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function cardsSection() {
  const title = await screen.findByText('Cartões', { selector: '[data-slot="card-title"]' })
  return title.closest<HTMLElement>('[data-slot="card"]')!
}

describe('DashboardPage, card de cartões', () => {
  beforeEach(() => {
    vi.mocked(api.summary.month).mockReset().mockResolvedValue(SUMMARY)
    vi.mocked(api.cards.list).mockReset().mockResolvedValue([CARD])
    vi.mocked(api.cards.invoice).mockReset().mockResolvedValue(AUGUST)
    vi.mocked(api.invoices.list).mockReset().mockResolvedValue({ imports: [], standby_count: 0, standby_cents: 0 })
  })

  it('mostra a fatura do mês filtrado, não a atual', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText('R$ 456,78')).toBeInTheDocument()
    expect(within(section).queryByText('R$ 999,00')).not.toBeInTheDocument()
    expect(within(section).getByText('Encerrada')).toBeInTheDocument()
    expect(within(section).getByText(/Vence em 12\/08\/2026/)).toBeInTheDocument()
    expect(api.cards.invoice).toHaveBeenCalledWith(7, '2026-08')
  })

  it('o limite usado continua sendo o de hoje', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText(/disponível R\$ 3\.800,00/)).toBeInTheDocument()
  })
})
