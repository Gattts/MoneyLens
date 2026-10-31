import type { Category, LimitAlert, LimitAlerts, LimitSuggestion, SpendingLimit } from '@/lib/types'

export function limit(overrides: Partial<SpendingLimit> = {}): SpendingLimit {
  return {
    id: 1,
    category_id: 1,
    name: 'Comida fora',
    icon: '🍔',
    amount_cents: 30_000,
    spent_cents: 10_000,
    percent: 33,
    p50_cents: 31_000,
    will_exceed: true,
    active: true,
    income_percent: null,
    income_cents: null,
    no_income: false,
    ...overrides,
  }
}

export function suggestion(overrides: Partial<LimitSuggestion> = {}): LimitSuggestion {
  return {
    suggested_cents: 31_000,
    low_cents: 28_000,
    high_cents: 34_000,
    months: 3,
    income_cents: 300_000,
    suggested_percent: 11,
    ...overrides,
  }
}

export function category(overrides: Partial<Category>): Category {
  return {
    id: 1,
    name: 'Comida fora',
    icon: '🍔',
    description: '',
    kind: 'expense',
    default_bucket: 'wants',
    archived: false,
    ...overrides,
  }
}

export function alert(overrides: Partial<LimitAlert> = {}): LimitAlert {
  return {
    id: 1,
    kind: 'reached_90',
    category_id: 1,
    name: 'Comida fora',
    icon: '🍔',
    spent_cents: 27_000,
    limit_cents: 30_000,
    forecast_cents: null,
    month: '2026-10',
    created_at: '2026-10-27T12:00:00Z',
    read_at: null,
    ...overrides,
  }
}

export function alerts(items: LimitAlert[]): LimitAlerts {
  return { unread: items.filter((item) => item.read_at === null).length, items }
}
