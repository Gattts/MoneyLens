import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'

import { TransactionDialog } from './TransactionDialog'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  const list = () => vi.fn().mockResolvedValue([])
  return {
    ...original,
    api: { ...original.api, categories: { list: list() }, cards: { list: list() }, goals: { list: list() } },
  }
})

function renderDialog(open: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <TransactionDialog open={open} onOpenChange={vi.fn()} month="2026-10" />
    </QueryClientProvider>,
  )
}

describe('TransactionDialog', () => {
  it('fechado, não busca nada no servidor', () => {
    renderDialog(false)
    expect(api.categories.list).not.toHaveBeenCalled()
    expect(api.cards.list).not.toHaveBeenCalled()
    expect(api.goals.list).not.toHaveBeenCalled()
  })

  it('aberto, busca categorias, cartões e metas para o formulário', async () => {
    renderDialog(true)
    await waitFor(() => expect(api.categories.list).toHaveBeenCalled())
    expect(api.cards.list).toHaveBeenCalled()
    expect(api.goals.list).toHaveBeenCalled()
  })
})
