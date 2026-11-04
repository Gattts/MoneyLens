import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'

import { ForecastPage } from './ForecastPage'
import { MODELS, forecast } from './test-data'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return { ...original, api: { ...original.api, forecast: { month: vi.fn(), models: vi.fn() } } }
})

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <ForecastPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ForecastPage', () => {
  beforeEach(() => {
    vi.mocked(api.forecast.month).mockReset().mockResolvedValue(forecast())
    vi.mocked(api.forecast.models).mockReset().mockResolvedValue(MODELS)
  })

  it('mostra cada categoria com gasto, provável, teto e estatística, e o selo de alerta', async () => {
    renderPage()
    const row = (await screen.findByText(/Comida fora/)).closest('tr')!
    expect(within(row).getByText('Acima do normal')).toBeInTheDocument()
    expect(within(row).getAllByText('R$ 250,00').length).toBeGreaterThan(0)
    expect(within(row).getByText('R$ 210,00')).toBeInTheDocument()
    const other = screen.getByText(/Mercado/).closest('tr')!
    expect(within(other).queryByText('Acima do normal')).not.toBeInTheDocument()
  })

  it('mostra o histórico de treinos com as métricas', async () => {
    renderPage()
    expect(await screen.findByText('Versão 2')).toBeInTheDocument()
    expect(screen.getByText('Em uso')).toBeInTheDocument()
    expect(screen.getByText('Erro médio do modelo: R$ 12,34')).toBeInTheDocument()
    expect(screen.getByText('Da estatística: R$ 20,00')).toBeInTheDocument()
    expect(screen.getByText('O máximo provável cobriu 88% dos casos')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Máximo provável' })).toBeInTheDocument()
  })

  it('sem modelo próprio, explica como treinar', async () => {
    vi.mocked(api.forecast.models).mockResolvedValue([])
    renderPage()
    expect(
      await screen.findByText('Usando o modelo base. Rode `financeiro treinar` com pelo menos 2 meses fechados.'),
    ).toBeInTheDocument()
  })
})

describe('ForecastPage, mês de pagamento', () => {
  beforeEach(() => {
    vi.mocked(api.forecast.month).mockReset().mockResolvedValue(forecast())
    vi.mocked(api.forecast.models).mockReset().mockResolvedValue(MODELS)
  })

  it('mostra o comprometido (faturas, parcelas e fixas do mês) em vez do gasto até agora', async () => {
    renderPage()
    const row = (await screen.findByText(/Mercado/)).closest('tr')!
    expect(screen.getByRole('columnheader', { name: 'Comprometido' })).toBeInTheDocument()
    expect(
      within(row).getByText('R$ 80,00', { normalizer: (text) => text.replace(/\u00a0/g, ' ') }),
    ).toBeInTheDocument()
    expect(screen.getByText(/compras no cartão contam no mês em que a fatura vence/)).toBeInTheDocument()
  })
})
