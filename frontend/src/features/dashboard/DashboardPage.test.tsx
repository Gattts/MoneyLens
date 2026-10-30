import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import type { Card, Invoice, MonthSummary } from '@/lib/types'

import { forecast } from '../forecast/test-data'
import { currentMonth } from '@/lib/dates'

import { DashboardPage } from './DashboardPage'

// formatCents separa "R$" do valor com espaço não separável.
const plain = (text: string | null) => (text ?? '').replace(/\u00a0/g, ' ')

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: {
      ...original.api,
      summary: { ...original.api.summary, month: vi.fn() },
      cards: { ...original.api.cards, list: vi.fn(), invoice: vi.fn() },
      invoices: { ...original.api.invoices, list: vi.fn() },
      forecast: { month: vi.fn(), models: vi.fn() },
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
    paid_cents: 0,
    remaining_cents: 99_900,
    paid_on: null,
  },
}
// Fecha no dia 5: as compras de agosto (de 05/08 em diante) caem na fatura que fecha em setembro.
const AUGUST_PURCHASES: Invoice = {
  card_id: 7,
  month: '2026-09',
  closing_date: '2026-09-05',
  due_date: '2026-09-12',
  period_start: '2026-08-05',
  period_end: '2026-09-04',
  total_cents: 45_678,
  status: 'paid',
  paid_cents: 45_678,
  remaining_cents: 0,
  paid_on: '2026-09-10',
  transactions: [],
  payments: [],
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
    vi.mocked(api.cards.invoice).mockReset().mockResolvedValue(AUGUST_PURCHASES)
    vi.mocked(api.invoices.list).mockReset().mockResolvedValue({ imports: [], standby_count: 0, standby_cents: 0 })
  })

  it('mostra a fatura com as compras do mês filtrado, não a atual', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText('R$ 456,78')).toBeInTheDocument()
    expect(within(section).queryByText('R$ 999,00')).not.toBeInTheDocument()
    expect(within(section).getByText('Paga em 10/09')).toBeInTheDocument()
    expect(within(section).getByText(/Vence em 12\/09\/2026/)).toBeInTheDocument()
    expect(api.cards.invoice).toHaveBeenCalledWith(7, '2026-09')
  })

  it('cartão que fecha depois do dia 15 mostra a fatura que fecha no próprio mês', async () => {
    vi.mocked(api.cards.list).mockResolvedValue([{ ...CARD, closing_day: 20, due_day: 28 }])
    renderAt('/?mes=2026-08')
    await cardsSection()
    await vi.waitFor(() => expect(api.cards.invoice).toHaveBeenCalledWith(7, '2026-08'))
  })

  it('o limite usado continua sendo o de hoje', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText(/disponível R\$ 3\.800,00/)).toBeInTheDocument()
  })
})

describe('DashboardPage, aviso de standby', () => {
  beforeEach(() => {
    vi.mocked(api.summary.month).mockReset().mockResolvedValue(SUMMARY)
    vi.mocked(api.cards.list).mockReset().mockResolvedValue([])
    vi.mocked(api.invoices.list).mockReset().mockResolvedValue({ imports: [], standby_count: 2, standby_cents: 5000 })
  })

  it('fala de importações, não só de faturas', async () => {
    renderAt('/?mes=2026-08')
    expect(await screen.findByText('Importações com itens em standby')).toBeInTheDocument()
    expect(screen.getByText('2 item(ns) em standby (R$ 50,00)')).toBeInTheDocument()
  })
})

describe('DashboardPage, previsão do mês', () => {
  beforeEach(() => {
    vi.mocked(api.summary.month).mockReset().mockResolvedValue(SUMMARY)
    vi.mocked(api.cards.list).mockReset().mockResolvedValue([])
    vi.mocked(api.invoices.list).mockReset().mockResolvedValue({ imports: [], standby_count: 0, standby_cents: 0 })
    vi.mocked(api.forecast.month).mockReset().mockResolvedValue(forecast())
  })

  it('no mês atual mostra o resumo: provável, gasto, teto e quantas categorias estão acima do normal', async () => {
    renderAt(`/?mes=${currentMonth()}`)
    const card = (await screen.findByText('Previsão do mês')).closest('[data-slot="card"]') as HTMLElement
    expect(await within(card).findByText('R$ 360,00')).toBeInTheDocument()
    expect(plain(within(card).getByText(/^Gasto até agora/).textContent)).toBe(
      'Gasto até agora R$ 300,00 · máximo provável R$ 450,00',
    )
    expect(within(card).getByText('1 categoria acima do normal')).toBeInTheDocument()
    expect(within(card).queryByText('Mercado')).not.toBeInTheDocument()
    expect(api.forecast.month).toHaveBeenCalled()
  })

  it('com menos de 3 meses fechados, o card diz que os dados são insuficientes', async () => {
    vi.mocked(api.forecast.month).mockResolvedValue(forecast({ history_months: 2 }))
    renderAt(`/?mes=${currentMonth()}`)
    expect(await screen.findByText('Dados insuficientes para prever.')).toBeInTheDocument()
    expect(screen.getByText('A previsão começa com 3 meses fechados de histórico; você tem 2.')).toBeInTheDocument()
    expect(screen.queryByText(/^Gasto até agora/)).not.toBeInTheDocument()
  })

  it('a coluna da direita empilha Fixas, Previsão e Cartões, sem buraco entre eles', async () => {
    renderAt(`/?mes=${currentMonth()}`)
    const forecastCard = await screen.findByText('Previsão do mês')
    const title = (name: string) => screen.getByText(name, { selector: '[data-slot="card-title"]' })
    const column = title('Fixas a confirmar').closest('[data-dashboard-column]') as HTMLElement
    expect(column).toContainElement(forecastCard)
    expect(column).toContainElement(title('Cartões'))
    expect(column).not.toContainElement(title('Orçamento do mês'))
    const order = [title('Fixas a confirmar'), forecastCard, title('Cartões')]
    expect(order[0].compareDocumentPosition(order[1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(order[1].compareDocumentPosition(order[2]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('em outro mês o card some e a previsão nem é buscada', async () => {
    renderAt('/?mes=2026-08')
    await screen.findByText('Cartões', { selector: '[data-slot="card-title"]' })
    expect(screen.queryByText('Previsão do mês')).not.toBeInTheDocument()
    expect(api.forecast.month).not.toHaveBeenCalled()
  })
})
