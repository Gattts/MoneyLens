import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useSingleFlight } from './useSingleFlight'

function deferred() {
  let resolve: () => void = () => {}
  let reject: (error: Error) => void = () => {}
  const promise = new Promise<void>((ok, fail) => {
    resolve = ok
    reject = fail
  })
  return { promise, resolve, reject }
}

describe('useSingleFlight', () => {
  it('ignora a segunda chamada enquanto a primeira não termina', async () => {
    const { result } = renderHook(() => useSingleFlight())
    const first = deferred()
    const task = vi.fn(() => first.promise)
    let running: Promise<unknown> = Promise.resolve()
    act(() => {
      running = result.current.run(task)
      void result.current.run(task)
    })
    expect(task).toHaveBeenCalledTimes(1)
    expect(result.current.pending).toBe(true)
    await act(async () => {
      first.resolve()
      await running
    })
    expect(result.current.pending).toBe(false)
    await act(() => result.current.run(task))
    expect(task).toHaveBeenCalledTimes(2)
  })

  it('libera a trava quando a tarefa falha', async () => {
    const { result } = renderHook(() => useSingleFlight())
    await act(async () => {
      await result.current.run(() => Promise.reject(new Error('falhou'))).catch(() => undefined)
    })
    const task = vi.fn(() => Promise.resolve())
    await act(() => result.current.run(task))
    expect(task).toHaveBeenCalledTimes(1)
  })
})
