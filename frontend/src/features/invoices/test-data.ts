import type { Category, InvoiceImportDetail, InvoiceLine } from '@/lib/types'

/** Linhas e categorias inventadas para os testes da tela da importação. */
export function line(overrides: Partial<InvoiceLine>): InvoiceLine {
  return {
    id: 1,
    position: 1,
    date: '2026-09-05',
    description: 'LOJA',
    merchant_key: 'LOJA',
    amount_cents: 1000,
    is_credit: false,
    installment_number: null,
    installment_total: null,
    payment_method: null,
    status: 'pending',
    skip_reason: null,
    category_id: null,
    rule_id: null,
    transaction_id: null,
    duplicate_of: null,
    payment_id: null,
    payment_suggestion: null,
    kind: overrides.is_credit ? 'income' : 'expense',
    ...overrides,
  }
}

export function category(overrides: Partial<Category>): Category {
  return {
    id: 10,
    name: 'Lazer',
    icon: '🏖️',
    description: '',
    kind: 'expense',
    default_bucket: 'wants',
    archived: false,
    ...overrides,
  } as Category
}

export function detail(overrides: Partial<InvoiceImportDetail>): InvoiceImportDetail {
  return {
    id: 5,
    source: 'card_invoice',
    card_id: 3,
    bank: 'inter',
    due_date: '2026-10-12',
    period_start: null,
    period_end: null,
    total_cents: 7390,
    confirmed_at: null,
    created_at: '2026-10-28T12:00:00Z',
    line_count: 0,
    pending_count: 0,
    pending_cents: 0,
    lines: [],
    investment: null,
    already_imported: false,
    ...overrides,
  }
}

/** Extrato da conta, com o período no lugar do cartão e do vencimento. */
export function statement(overrides: Partial<InvoiceImportDetail>): InvoiceImportDetail {
  return detail({
    source: 'account_statement',
    bank: 'nubank',
    card_id: null,
    due_date: null,
    period_start: '2026-10-01',
    period_end: '2026-10-27',
    investment: { applied_cents: 0, redeemed_cents: 0 },
    ...overrides,
  })
}
