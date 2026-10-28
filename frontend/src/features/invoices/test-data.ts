import type { Category, InvoiceImportDetail, InvoiceLine } from '@/lib/types'

/** Linhas e categorias inventadas para os testes da tela da fatura. */
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
    status: 'pending',
    skip_reason: null,
    category_id: null,
    rule_id: null,
    transaction_id: null,
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
    card_id: 3,
    bank: 'inter',
    due_date: '2026-10-12',
    total_cents: 7390,
    confirmed_at: null,
    created_at: '2026-10-28T12:00:00Z',
    line_count: 0,
    pending_count: 0,
    pending_cents: 0,
    lines: [],
    already_imported: false,
    ...overrides,
  }
}
