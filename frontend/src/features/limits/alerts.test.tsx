import { addMonths, currentMonth, formatMonthShort } from '@/lib/dates'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { toast } from 'sonner'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { keys } from '@/lib/queries'

import { AlertBanner } from './AlertBanner'
import { AlertBell } from './AlertBell'
import { AlertsProvider } from './AlertsPanel'
import { LimitsCard } from './LimitsCard'
import { alertMessage } from './limit-labels'
import { alert, alerts, limit } from './test-data'
import { useAlertToast } from './useAlertToast'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: {
      ...original.api,
      alerts: { list: vi.fn(), read: vi.fn() },
      limits: { ...original.api.limits, list: vi.fn() },
    },
  }
})
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }))

// formatCents separa "R$" do valor com espaço não separável.
const plain = (text: string | null) => (text ?? '').replace(/\u00a0/g, ' ')

function renderWith(children: ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AlertsProvider>{children}</AlertsProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function ToastProbe() {
  useAlertToast()
  return null
}

const FOUR = [
  alert({ id: 1, name: 'Comida fora' }),
  alert({ id: 2, name: 'Delivery', kind: 'reached_50' }),
  alert({ id: 3, name: 'Lazer', kind: 'reached_100', spent_cents: 31_500 }),
  alert({ id: 4, name: 'Mercado', kind: 'forecast', spent_cents: 20_000, forecast_cents: 34_000 }),
]

describe('alertas de teto', () => {
  beforeEach(() => {
    vi.mocked(api.alerts.list)
      .mockReset()
      .mockResolvedValue(alerts(FOUR.slice(0, 2)))
    vi.mocked(api.alerts.read)
      .mockReset()
      .mockResolvedValue(alerts(FOUR.slice(0, 2).map((item) => ({ ...item, read_at: '2026-10-27T13:00:00Z' }))))
    vi.mocked(api.limits.list).mockReset().mockResolvedValue([])
    vi.mocked(toast).mockReset()
    sessionStorage.clear()
  })

  it('alertMessage monta os quatro textos', () => {
    expect(plain(alertMessage(alert({ kind: 'reached_50', spent_cents: 15_000 })))).toBe(
      'Comida fora chegou a 50% do teto: R$ 150,00 de R$ 300,00.',
    )
    expect(plain(alertMessage(alert()))).toBe('Comida fora chegou a 90% do teto: R$ 270,00 de R$ 300,00.')
    expect(plain(alertMessage(alert({ kind: 'reached_100', spent_cents: 31_500 })))).toBe(
      'Comida fora passou do teto: R$ 315,00 de R$ 300,00.',
    )
    expect(plain(alertMessage(alert({ kind: 'forecast', spent_cents: 20_000, forecast_cents: 34_000 })))).toBe(
      'Comida fora deve passar do teto: previsão de R$ 340,00 para R$ 300,00.',
    )
  })

  it('o sino mostra a contagem e abrir o painel marca como lidos', async () => {
    const user = userEvent.setup()
    renderWith(<AlertBell />)
    const bell = await screen.findByRole('button', { name: 'Alertas de teto' })
    expect(await within(bell).findByText('2')).toBeInTheDocument()
    await user.click(bell)
    expect(vi.mocked(api.alerts.read)).toHaveBeenCalledWith()
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText(/Comida fora chegou a 90% do teto/)).toBeInTheDocument()
    await vi.waitFor(() => expect(within(bell).queryByText('2')).not.toBeInTheDocument())
  })

  it('o sino sem alertas não mostra número e o painel diz que não há nada', async () => {
    vi.mocked(api.alerts.list).mockResolvedValue(alerts([]))
    const user = userEvent.setup()
    renderWith(<AlertBell />)
    const bell = await screen.findByRole('button', { name: 'Alertas de teto' })
    expect(bell.textContent).toBe('')
    await user.click(bell)
    expect(await screen.findByText('Nenhum alerta ainda.')).toBeInTheDocument()
    expect(vi.mocked(api.alerts.read)).not.toHaveBeenCalled()
  })

  it('o aviso do Painel mostra até 3 não lidos e Ver todos abre o painel', async () => {
    vi.mocked(api.alerts.list).mockResolvedValue(alerts(FOUR))
    const user = userEvent.setup()
    renderWith(<AlertBanner />)
    expect(await screen.findByText(/Comida fora chegou a 90%/)).toBeInTheDocument()
    expect(screen.getByText(/Delivery chegou a 50%/)).toBeInTheDocument()
    expect(screen.getByText(/Lazer passou do teto/)).toBeInTheDocument()
    expect(screen.queryByText(/Mercado deve passar/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ver todos' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('o aviso do Painel some sem alertas não lidos', async () => {
    vi.mocked(api.alerts.list).mockResolvedValue(alerts([alert({ read_at: '2026-10-27T13:00:00Z' })]))
    const { container } = renderWith(<AlertBanner />)
    await vi.waitFor(() => expect(vi.mocked(api.alerts.list)).toHaveBeenCalled())
    expect(container.textContent).toBe('')
  })

  it('o card mostra os 5 tetos ativos de maior percentual e some sem tetos', async () => {
    const names = ['Lazer', 'Delivery', 'Mercado', 'Comida fora', 'Farmácia', 'Transporte']
    vi.mocked(api.limits.list).mockResolvedValue([
      ...names.map((name, index) => limit({ id: index + 1, category_id: index + 1, name, percent: 90 - index * 10 })),
      limit({ id: 9, category_id: 9, name: 'Antiga', active: false }),
    ])
    renderWith(<LimitsCard />)
    expect(await screen.findByText('Tetos do mês')).toBeInTheDocument()
    for (const name of names.slice(0, 5)) expect(screen.getByText(name)).toBeInTheDocument()
    expect(screen.queryByText('Transporte')).not.toBeInTheDocument()
    expect(screen.queryByText('Antiga')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ver tetos' })).toHaveAttribute('href', '/tetos')
  })

  it('o card some quando não há teto ativo', async () => {
    vi.mocked(api.limits.list).mockResolvedValue([limit({ active: false })])
    const { container } = renderWith(<LimitsCard />)
    await vi.waitFor(() => expect(vi.mocked(api.limits.list)).toHaveBeenCalled())
    expect(container.textContent).toBe('')
  })

  it('o aviso ao entrar aparece uma vez por sessão', async () => {
    const first = renderWith(<ToastProbe />)
    await vi.waitFor(() => expect(vi.mocked(toast)).toHaveBeenCalledWith('Você tem 2 alertas de teto'))
    first.unmount()
    renderWith(<ToastProbe />)
    await vi.waitFor(() => expect(vi.mocked(api.alerts.list)).toHaveBeenCalledTimes(2))
    expect(vi.mocked(toast)).toHaveBeenCalledTimes(1)
  })

  it('um alerta novo durante a sessão aparece num aviso rápido com o texto dele', async () => {
    vi.mocked(api.alerts.list).mockResolvedValue(alerts([alert({ id: 1 })]))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <ToastProbe />
      </QueryClientProvider>,
    )
    await vi.waitFor(() => expect(vi.mocked(toast)).toHaveBeenCalledWith('Você tem 1 alerta de teto'))
    vi.mocked(api.alerts.list).mockResolvedValue(
      alerts([alert({ id: 2, kind: 'reached_100', spent_cents: 31_500 }), alert({ id: 1 })]),
    )
    await act(() => client.invalidateQueries({ queryKey: keys.alerts }))
    await vi.waitFor(() => expect(vi.mocked(toast)).toHaveBeenCalledTimes(2))
    expect(plain(vi.mocked(toast).mock.calls[1][0] as string)).toBe(
      'Comida fora passou do teto: R$ 315,00 de R$ 300,00.',
    )
  })

  it('o aviso ao entrar fala no singular com um alerta', async () => {
    vi.mocked(api.alerts.list).mockResolvedValue(alerts([alert()]))
    renderWith(<ToastProbe />)
    await vi.waitFor(() => expect(vi.mocked(toast)).toHaveBeenCalledWith('Você tem 1 alerta de teto'))
  })
})

describe('alerta de um mês seguinte', () => {
  it('cita o mês do teto quando não é o atual', () => {
    const later = addMonths(currentMonth(), 1)
    const text = plain(alertMessage(alert({ kind: 'reached_90', spent_cents: 27_000, month: later })))
    expect(text).toBe(`Comida fora chegou a 90% do teto de ${formatMonthShort(later)}: R$ 270,00 de R$ 300,00.`)
  })
})
