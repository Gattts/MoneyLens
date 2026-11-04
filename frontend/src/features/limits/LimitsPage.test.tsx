import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'
import { addMonths, currentMonth } from '@/lib/dates'

import { LimitsPage } from './LimitsPage'
import { category, limit, suggestion } from './test-data'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: {
      ...original.api,
      categories: { ...original.api.categories, list: vi.fn() },
      limits: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), suggestion: vi.fn() },
    },
  }
})

// formatCents separa "R$" do valor com espaço não separável.
const plain = (text: string | null) => (text ?? '').replace(/\u00a0/g, ' ')

const CATEGORIES = [
  category({ id: 1, name: 'Comida fora' }),
  category({ id: 2, name: 'Mercado', icon: '🛒' }),
  category({ id: 3, name: 'Antiga', archived: true }),
  category({ id: 4, name: 'Salário', kind: 'income', default_bucket: null }),
  category({ id: 5, name: 'Delivery', icon: '🛵' }),
]

function renderPage() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <LimitsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function openNewLimit() {
  const user = userEvent.setup()
  renderPage()
  await user.click(await screen.findByRole('button', { name: /Novo teto/ }))
  return user
}

describe('LimitsPage', () => {
  beforeEach(() => {
    vi.mocked(api.categories.list).mockReset().mockResolvedValue(CATEGORIES)
    vi.mocked(api.limits.list)
      .mockReset()
      .mockResolvedValue([
        limit(),
        limit({ id: 2, category_id: 2, name: 'Mercado', icon: '🛒', percent: 0, spent_cents: 0, will_exceed: false }),
        limit({ id: 3, category_id: 3, name: 'Antiga', active: false, will_exceed: false, p50_cents: null }),
        limit({
          id: 4,
          category_id: 4,
          name: 'Lazer',
          icon: '🏖️',
          income_percent: 15,
          income_cents: 0,
          amount_cents: 0,
          percent: 0,
          active: false,
          no_income: true,
          will_exceed: false,
        }),
      ])
    vi.mocked(api.limits.suggestion).mockReset().mockResolvedValue(suggestion())
    vi.mocked(api.limits.create).mockReset().mockResolvedValue(limit())
  })

  it('lista os tetos com gasto, percentual e selos', async () => {
    renderPage()
    const food = (await screen.findByText('Comida fora')).closest('[data-limit]') as HTMLElement
    expect(plain(within(food).getByText(/de R\$/).textContent)).toBe('R$ 100,00 de R$ 300,00')
    expect(within(food).getByText('33%')).toBeInTheDocument()
    expect(within(food).getByText('Vai estourar')).toBeInTheDocument()
    expect(within(food).getByLabelText(/^Previsão:/)).toBeInTheDocument()
    const market = screen.getByText('Mercado').closest('[data-limit]') as HTMLElement
    expect(within(market).queryByText('Vai estourar')).not.toBeInTheDocument()
    const old = screen.getByText('Antiga').closest('[data-limit]') as HTMLElement
    expect(within(old).getByText('Inativo')).toBeInTheDocument()
    const leisure = screen.getByText('Lazer').closest('[data-limit]') as HTMLElement
    expect(within(leisure).getByText('15% da renda prevista')).toBeInTheDocument()
    expect(within(leisure).getByText('Sem renda neste mês')).toBeInTheDocument()
    expect(within(leisure).queryByText('Inativo')).not.toBeInTheDocument()
  })

  it('teto por porcentagem mostra quanto vale no mês e salva a porcentagem', async () => {
    const user = await openNewLimit()
    await user.selectOptions(screen.getByLabelText('Categoria'), '5')
    await user.click(screen.getByLabelText('% da renda'))
    await user.type(screen.getByLabelText('Porcentagem da renda'), '15')
    const worth = await screen.findByText(/da renda prevista =/)
    expect(plain(worth.textContent)).toBe('15% da renda prevista = R$ 450,00 neste mês')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(vi.mocked(api.limits.create)).toHaveBeenCalledWith({ category_id: 5, income_percent: 15 })
  })

  it('no modo porcentagem, a sugestão vem em % e Usar sugestão preenche a porcentagem', async () => {
    const user = await openNewLimit()
    await user.selectOptions(screen.getByLabelText('Categoria'), '5')
    await user.click(screen.getByLabelText('% da renda'))
    const hint = await screen.findByText(/^Sugestão:/)
    expect(plain(hint.textContent)).toBe('Sugestão: 11% da renda (R$ 310,00) · você costuma gastar R$ 280,00–R$ 340,00')
    await user.click(screen.getByRole('button', { name: 'Usar sugestão' }))
    expect(screen.getByLabelText('Porcentagem da renda')).toHaveValue('11')
  })

  it('editar um teto por porcentagem abre na porcentagem', async () => {
    vi.mocked(api.limits.list).mockResolvedValue([
      limit({ income_percent: 15, income_cents: 300_000, amount_cents: 45_000 }),
    ])
    vi.mocked(api.limits.update).mockReset().mockResolvedValue(limit())
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: /Editar/ }))
    expect(screen.getByLabelText('% da renda')).toBeChecked()
    const field = screen.getByLabelText('Porcentagem da renda')
    expect(field).toHaveValue('15')
    await user.clear(field)
    await user.type(field, '20')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(vi.mocked(api.limits.update)).toHaveBeenCalledWith(1, { income_percent: 20 })
  })

  it('novo teto mostra a sugestão e Usar sugestão preenche o valor', async () => {
    const user = await openNewLimit()
    await user.selectOptions(screen.getByLabelText('Categoria'), '5')
    expect(vi.mocked(api.limits.suggestion)).toHaveBeenCalledWith(5)
    const hint = await screen.findByText(/^Sugestão:/)
    expect(plain(hint.textContent)).toBe('Sugestão: R$ 310,00 · você costuma gastar R$ 280,00–R$ 340,00')
    await user.click(screen.getByRole('button', { name: 'Usar sugestão' }))
    expect(screen.getByLabelText('Valor do teto')).toHaveValue('310,00')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))
    expect(vi.mocked(api.limits.create)).toHaveBeenCalledWith({ category_id: 5, amount_cents: 31_000 })
  })

  it('sem histórico mostra a mensagem', async () => {
    vi.mocked(api.limits.suggestion).mockResolvedValue(suggestion({ suggested_cents: null, months: 0 }))
    const user = await openNewLimit()
    await user.selectOptions(screen.getByLabelText('Categoria'), '5')
    expect(
      await screen.findByText('Sem histórico ainda: informe o valor. Depois do primeiro mês eu sugiro.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Usar sugestão' })).not.toBeInTheDocument()
  })

  it('o cadastro só oferece categorias de despesa ativas e sem teto', async () => {
    await openNewLimit()
    const options = within(screen.getByLabelText('Categoria'))
      .getAllByRole('option')
      .map((option) => option.textContent)
    expect(options).toEqual(['Escolha…', '🛵 Delivery'])
  })
})

describe('LimitsPage, mês de pagamento', () => {
  beforeEach(() => {
    vi.mocked(api.categories.list).mockReset().mockResolvedValue(CATEGORIES)
    vi.mocked(api.limits.list).mockReset().mockResolvedValue([limit()])
  })

  it('abre no mês atual e navega para o seguinte (compras no cartão pagas depois)', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Comida fora')
    expect(api.limits.list).toHaveBeenCalledWith(currentMonth())
    await user.click(screen.getByRole('button', { name: 'Próximo mês' }))
    await vi.waitFor(() => expect(api.limits.list).toHaveBeenCalledWith(addMonths(currentMonth(), 1)))
  })

  it('explica que a compra no cartão conta no mês da fatura', async () => {
    renderPage()
    expect(await screen.findByText(/compras no cartão contam no mês em que a fatura vence/)).toBeInTheDocument()
  })
})
