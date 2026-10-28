import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { useQuickAction } from './useCrud'

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
}

describe('useQuickAction', () => {
  it('dois cliques seguidos disparam a ação uma vez só', async () => {
    const action = vi.fn(() => new Promise<void>(() => {}))
    const { result } = renderHook(() => useQuickAction(action, () => 'Feito.'), { wrapper })
    await act(async () => {
      result.current.mutate(1)
      result.current.mutate(1)
    })
    expect(action).toHaveBeenCalledTimes(1)
  })
})
