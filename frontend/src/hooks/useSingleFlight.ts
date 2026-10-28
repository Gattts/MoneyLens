import { useCallback, useRef, useState } from 'react'

/**
 * Uma execução por vez. O 2º clique de um clique duplo chega antes de o botão desabilitar (o estado do React e o
 * `isPending` do TanStack Query só mudam depois), então a trava é síncrona, numa ref. `pending` serve para a tela.
 */
export function useSingleFlight() {
  const running = useRef(false)
  const [pending, setPending] = useState(false)
  const run = useCallback(async <T>(task: () => Promise<T>): Promise<T | undefined> => {
    if (running.current) return undefined
    running.current = true
    setPending(true)
    try {
      return await task()
    } finally {
      running.current = false
      setPending(false)
    }
  }, [])
  return { run, pending }
}
