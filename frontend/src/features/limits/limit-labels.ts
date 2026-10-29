import { formatCents } from '@/lib/money'
import type { LimitAlert, LimitSuggestion } from '@/lib/types'

export const NO_HISTORY = 'Sem histórico ainda: informe o valor. Depois do primeiro mês eu sugiro.'

/** "Sugestão: R$ 310,00 · você costuma gastar R$ 280,00–R$ 340,00" (null sem histórico). */
export function suggestionText(suggestion: LimitSuggestion): string | null {
  if (suggestion.suggested_cents === null) return null
  const range = `${formatCents(suggestion.low_cents)}–${formatCents(suggestion.high_cents)}`
  return `Sugestão: ${formatCents(suggestion.suggested_cents)} · você costuma gastar ${range}`
}

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
