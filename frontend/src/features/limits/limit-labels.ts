import { formatCents } from '@/lib/money'
import type { LimitAlert, LimitSuggestion } from '@/lib/types'

export const NO_HISTORY = 'Sem histórico ainda: informe o valor. Depois do primeiro mês eu sugiro.'

export const NO_INCOME = 'Sem renda prevista neste mês: o teto por porcentagem fica inativo até ela entrar.'

export type LimitBasis = 'amount' | 'percent'

/**
 * "Sugestão: R$ 310,00 · você costuma gastar R$ 280,00–R$ 340,00", ou em % da renda no modo porcentagem.
 * Null quando não há o que sugerir (sem histórico, ou em % sem renda prevista).
 */
export function suggestionText(suggestion: LimitSuggestion, basis: LimitBasis = 'amount'): string | null {
  if (suggestion.suggested_cents === null) return null
  const range = `você costuma gastar ${formatCents(suggestion.low_cents)}–${formatCents(suggestion.high_cents)}`
  if (basis === 'amount') return `Sugestão: ${formatCents(suggestion.suggested_cents)} · ${range}`
  if (suggestion.suggested_percent === null) return null
  return `Sugestão: ${suggestion.suggested_percent}% da renda (${formatCents(suggestion.suggested_cents)}) · ${range}`
}

/** Quanto vale um teto por porcentagem neste mês (a mesma conta do servidor: arredonda para baixo). */
export const percentOf = (incomeCents: number, percent: number) => Math.floor((incomeCents * percent) / 100)

/** O texto de um alerta de teto, como aparece no sino, no Painel e na notificação. */
export function alertMessage(alert: LimitAlert): string {
  const spent = formatCents(alert.spent_cents)
  const limit = formatCents(alert.limit_cents)
  switch (alert.kind) {
    case 'reached_50':
      return `${alert.name} chegou a 50% do teto: ${spent} de ${limit}.`
    case 'reached_90':
      return `${alert.name} chegou a 90% do teto: ${spent} de ${limit}.`
    case 'reached_100':
      return `${alert.name} passou do teto: ${spent} de ${limit}.`
    case 'forecast':
      return `${alert.name} deve passar do teto: previsão de ${formatCents(alert.forecast_cents ?? 0)} para ${limit}.`
  }
}
