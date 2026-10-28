import { useEffect, useState } from 'react'

/** Devolve `value` só depois de `delayMs` sem mudanças (evita uma busca por tecla digitada). */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
