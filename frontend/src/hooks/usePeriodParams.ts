import { useSearchParams } from 'react-router'

import { currentMonth } from '@/lib/dates'
import { isMonthText } from '@/lib/validation'

/**
 * Mês e ano ficam na URL (?mes=2026-10, ?ano=2026): recarregar a página, voltar no navegador ou
 * compartilhar o link mantém o período escolhido. Valor inválido na URL cai no período atual.
 */
export function useMonthParam(): [string, (month: string) => void] {
  const [params, setParams] = useSearchParams()
  const raw = params.get('mes') ?? ''
  const month = isMonthText(raw) ? raw : currentMonth()
  const setMonth = (next: string) =>
    setParams((previous) => {
      const updated = new URLSearchParams(previous)
      updated.set('mes', next)
      return updated
    })
  return [month, setMonth]
}

export function useYearParam(): [number, (year: number) => void] {
  const [params, setParams] = useSearchParams()
  const raw = Number(params.get('ano'))
  const year = Number.isInteger(raw) && raw >= 2000 && raw <= 2100 ? raw : new Date().getFullYear()
  const setYear = (next: number) => setParams({ ano: String(next) })
  return [year, setYear]
}
