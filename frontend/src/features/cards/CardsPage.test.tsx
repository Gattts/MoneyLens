import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'

import { CardsPage } from './CardsPage'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return { ...original, api: { ...original.api, cards: { ...original.api.cards, list: vi.fn() } } }
})

describe('CardsPage', () => {
  it('avisa que a compra no cartão conta no mês em que a fatura vence', async () => {
    vi.mocked(api.cards.list).mockResolvedValue([])
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter>
          <CardsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(
      await screen.findByText(/cada compra no cartão já conta como gasto no mês em que a fatura vence/),
    ).toBeInTheDocument()
  })
})
