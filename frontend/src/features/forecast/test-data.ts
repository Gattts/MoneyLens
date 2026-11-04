import type { Forecast, ForecastModelInfo } from '@/lib/types'

/** Previsão inventada para os testes das telas. */
export function forecast(overrides: Partial<Forecast> = {}): Forecast {
  return {
    month: '2026-10',
    day: 27,
    source: 'base_model',
    history_months: 3,
    total: { spent_cents: 30_000, committed_cents: 33_000, p50_cents: 36_000, p90_cents: 45_000 },
    categories: [
      {
        category_id: 1,
        name: 'Comida fora',
        icon: '🍽️',
        spent_cents: 25_000,
        committed_cents: 25_000,
        p50_cents: 25_000,
        p90_cents: 25_000,
        baseline_cents: 21_000,
        source: 'base_model',
        alert: true,
        alert_reason: 'above',
      },
      {
        category_id: 2,
        name: 'Mercado',
        icon: '🛒',
        spent_cents: 5_000,
        committed_cents: 8_000,
        p50_cents: 11_000,
        p90_cents: 20_000,
        baseline_cents: 9_000,
        source: 'base_model',
        alert: false,
        alert_reason: null,
      },
    ],
    ...overrides,
  }
}

export const MODELS: ForecastModelInfo[] = [
  {
    version: 2,
    trained_at: '2026-10-28T20:00:00Z',
    trained_until: '2026-09',
    feature_version: 1,
    metrics: { mae_model_cents: 1_234, mae_baseline_cents: 2_000, coverage_p90: 0.875, months: 3 },
    active: true,
  },
]
