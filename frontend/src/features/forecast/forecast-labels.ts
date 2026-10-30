import type { CategoryForecast } from '@/lib/types'

export const SOURCE_LABELS = { model: 'seu modelo', base_model: 'modelo base' } as const
export const SHOWN = 6
export const MIN_HISTORY_MONTHS = 3 // abaixo disso, o Painel não resume a previsão

/** Alertas primeiro; depois as categorias com mais gasto previsto. */
export const byAttention = (a: CategoryForecast, b: CategoryForecast) =>
  Number(b.alert) - Number(a.alert) || b.p50_cents - a.p50_cents
