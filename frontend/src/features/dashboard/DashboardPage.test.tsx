import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import type { Card, Invoice, MonthSummary } from '@/lib/types'

import { forecast } from '../forecast/test-data'
import { addMonths, currentMonth } from '@/lib/dates'

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
  deferred: [],
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
// Fecha no dia 5 e vence no dia 12: a fatura que vence em agosto é a que fecha em agosto.
const AUGUST_DUE: Invoice = {
  card_id: 7,
  month: '2026-08',
  closing_date: '2026-08-05',
  due_date: '2026-08-12',
  period_start: '2026-07-05',
  period_end: '2026-08-04',
  total_cents: 45_678,
  status: 'paid',
  paid_cents: 45_678,
  remaining_cents: 0,
  paid_on: '2026-08-10',
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
    vi.mocked(api.cards.invoice).mockReset().mockResolvedValue(AUGUST_DUE)
    vi.mocked(api.invoices.list).mockReset().mockResolvedValue({ imports: [], standby_count: 0, standby_cents: 0 })
  })

  it('mostra a fatura que vence no mês filtrado', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText('R$ 456,78')).toBeInTheDocument()
    expect(within(section).getByText('Paga em 10/08')).toBeInTheDocument()
    expect(within(section).getByText(/Vence em 12\/08\/2026/)).toBeInTheDocument()
    expect(api.cards.invoice).toHaveBeenCalledWith(7, '2026-08')
  })

  it('cartão que vence depois do mês do fechamento (fecha 29, vence 5) mostra a fatura que fechou no mês anterior', async () => {
    vi.mocked(api.cards.list).mockResolvedValue([{ ...CARD, closing_day: 29, due_day: 5 }])
    renderAt('/?mes=2026-08')
    await cardsSection()
    await vi.waitFor(() => expect(api.cards.invoice).toHaveBeenCalledWith(7, '2026-07'))
  })

  it('no mês atual, mostra também a fatura aberta quando ela é outra', async () => {
    const month = currentMonth()
    const open = {
      ...CARD.current_invoice,
      month,
      closing_date: `${month}-29`,
      due_date: `${addMonths(month, 1)}-05`,
      total_cents: 99_900,
    }
    vi.mocked(api.cards.list).mockResolvedValue([{ ...CARD, closing_day: 29, due_day: 5, current_invoice: open }])
    vi.mocked(api.cards.invoice).mockResolvedValue({ ...AUGUST_DUE, month: addMonths(month, -1) })
    renderAt(`/?mes=${month}`)
    const section = await cardsSection()
    const line = await within(section).findByText(/Aberta agora/)
    expect(plain(line.textContent)).toBe(
      `Aberta agora: R$ 999,00 · fecha 29/${month.slice(5)} · vence 05/${addMonths(month, 1).slice(5)}`,
    )
  })

  it('sem a linha extra quando a fatura que vence no mês já é a aberta', async () => {
    const month = currentMonth()
    vi.mocked(api.cards.list).mockResolvedValue([{ ...CARD, current_invoice: { ...CARD.current_invoice, month } }])
    vi.mocked(api.cards.invoice).mockResolvedValue({ ...AUGUST_DUE, month })
    renderAt(`/?mes=${month}`)
    const section = await cardsSection()
    expect(await within(section).findByText('R$ 456,78')).toBeInTheDocument()
    expect(within(section).queryByText(/Aberta agora/)).not.toBeInTheDocument()
  })

  it('fatura aberta mostra o fechamento e o vencimento', async () => {
    const open: Invoice = { ...AUGUST_DUE, status: 'open', paid_cents: 0, remaining_cents: 45_678, paid_on: null }
    vi.mocked(api.cards.invoice).mockResolvedValue(open)
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText(/^Fecha em 05\/08\/2026 · vence em 12\/08\/2026/)).toBeInTheDocument()
  })

  it('fatura paga mostra só o vencimento', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText(/^Vence em 12\/08\/2026/)).toBeInTheDocument()
    expect(within(section).queryByText(/Fecha em/)).not.toBeInTheDocument()
  })

  it('em outro mês, não mostra a fatura aberta agora', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText('R$ 456,78')).toBeInTheDocument()
    expect(within(section).queryByText(/Aberta agora/)).not.toBeInTheDocument()
    expect(within(section).queryByText('R$ 999,00')).not.toBeInTheDocument()
  })

  it('o limite usado continua sendo o de hoje', async () => {
    renderAt('/?mes=2026-08')
    const section = await cardsSection()
    expect(await within(section).findByText(/disponível R\$ 3\.800,00/)).toBeInTheDocument()
  })
})

describe('DashboardPage, para onde foi o dinheiro', () => {
  beforeEach(() => {
    vi.mocked(api.cards.list).mockReset().mockResolvedValue([])
    vi.mocked(api.invoices.list).mockReset().mockResolvedValue({ imports: [], standby_count: 0, standby_cents: 0 })
  })

  it('mostra todas as categorias com gasto, não só as 8 maiores', async () => {
    const by_category = Array.from({ length: 11 }, (_, index) => ({
      category_id: index + 1,
      name: `Categoria ${index + 1}`,
      icon: '',
      total_cents: (12 - index) * 1_000,
    }))
    vi.mocked(api.summary.month)
      .mockReset()
      .mockResolvedValue({ ...SUMMARY, by_category })
    renderAt('/?mes=2026-08')
    const title = await screen.findByText('Para onde foi o dinheiro', { selector: '[data-slot="card-title"]' })
    const section = title.closest<HTMLElement>('[data-slot="card"]')!
    expect(await within(section).findByText('Categoria 11')).toBeInTheDocument()
    expect(within(section).getAllByText(/^Categoria \d+$/)).toHaveLength(11)
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
    expect(plain(within(card).getByText(/^Já comprometido/).textContent)).toBe(
      'Já comprometido R$ 330,00 · máximo provável R$ 450,00',
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
    expect(screen.queryByText(/^Já comprometido/)).not.toBeInTheDocument()
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

describe('DashboardPage, mês de pagamento', () => {
  const sectionOf = async (title: string) =>
    (await screen.findByText(title, { selector: '[data-slot="card-title"]' })).closest<HTMLElement>(
      '[data-slot="card"]',
    )!

  beforeEach(() => {
    vi.mocked(api.cards.list).mockReset().mockResolvedValue([])
    vi.mocked(api.invoices.list).mockReset().mockResolvedValue({ imports: [], standby_count: 0, standby_cents: 0 })
  })

  it('"Para pagar depois" mostra as compras do mês que entram em faturas seguintes', async () => {
    const deferred = [{ card_id: 7, card_name: 'PicPay', payment_month: '2026-12', total_cents: 31_905 }]
    vi.mocked(api.summary.month)
      .mockReset()
      .mockResolvedValue({ ...SUMMARY, deferred })
    renderAt('/?mes=2026-08')
    const section = await sectionOf('Para pagar depois')
    expect(within(section).getByText('PicPay')).toBeInTheDocument()
    expect(plain(within(section).getByText(/entra em/).textContent)).toBe('R$ 319,05 · entra em dez/2026')
  })

  it('sem compras para depois, o card some', async () => {
    vi.mocked(api.summary.month).mockReset().mockResolvedValue(SUMMARY)
    renderAt('/?mes=2026-08')
    await sectionOf('Para onde foi o dinheiro')
    expect(screen.queryByText('Para pagar depois')).not.toBeInTheDocument()
  })

  it('fixa no cartão diz em que mês entra; o resto não', async () => {
    const pending = [
      {
        rule_id: 1,
        description: 'Streaming',
        kind: 'expense' as const,
        amount_cents: 2_000,
        date: '2026-08-20',
        category_id: 1,
        bucket: 'wants' as const,
        payment_method: 'credit_card' as const,
        card_id: 7,
        payment_month: '2026-09',
      },
      {
        rule_id: 2,
        description: 'Aluguel',
        kind: 'expense' as const,
        amount_cents: 150_000,
        date: '2026-08-10',
        category_id: 1,
        bucket: 'needs' as const,
        payment_method: 'bank_slip' as const,
        card_id: null,
        payment_month: '2026-08',
      },
    ]
    vi.mocked(api.summary.month)
      .mockReset()
      .mockResolvedValue({ ...SUMMARY, pending })
    renderAt('/?mes=2026-08')
    const section = await sectionOf('Fixas a confirmar')
    expect(within(section).getAllByText(/entra em/)).toHaveLength(1)
    expect(within(section).getByText(/entra em set\/2026/)).toBeInTheDocument()
  })

  it('os textos explicam a regra: gasto previsto inclui faturas e o cartão entra no mês da fatura', async () => {
    const pendingFlow = { realized_cents: 0, pending_cents: 30_000, total_cents: 30_000 }
    vi.mocked(api.summary.month)
      .mockReset()
      .mockResolvedValue({ ...SUMMARY, needs: pendingFlow })
    renderAt('/?mes=2026-08')
    expect(await screen.findByText(/ainda previsto \(faturas a pagar e fixas a confirmar\)/)).toBeInTheDocument()
    expect(screen.getByText(/compras no cartão entram no mês em que a fatura vence/)).toBeInTheDocument()
  })
})
