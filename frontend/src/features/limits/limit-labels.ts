import { formatCents } from '@/lib/money'
import type { LimitSuggestion } from '@/lib/types'

export const NO_HISTORY = 'Sem histórico ainda: informe o valor. Depois do primeiro mês eu sugiro.'

/** "Sugestão: R$ 310,00 · você costuma gastar R$ 280,00–R$ 340,00" (null sem histórico). */
export function suggestionText(suggestion: LimitSuggestion): string | null {
  if (suggestion.suggested_cents === null) return null
  const range = `${formatCents(suggestion.low_cents)}–${formatCents(suggestion.high_cents)}`
  return `Sugestão: ${formatCents(suggestion.suggested_cents)} · você costuma gastar ${range}`
}
