import { describe, expect, it } from 'vitest'

import { invoiceStatusText } from './invoice-status'

// formatCents separa "R$" do valor com espaço não separável.
const plain = (text: string) => text.replace(/\u00a0/g, ' ')

describe('invoiceStatusText', () => {
  it.each([
    [{ status: 'paid', paid_on: '2026-11-05', remaining_cents: 0 }, 'Paga em 05/11'],
    [{ status: 'paid', paid_on: null, remaining_cents: 0 }, 'Paga'],
    [{ status: 'partially_paid', paid_on: '2026-11-05', remaining_cents: 4000 }, 'Paga em parte (faltam R$ 40,00)'],
    [{ status: 'overdue', paid_on: null, remaining_cents: 100 }, 'Vencida, sem pagamento'],
    [{ status: 'paid_before_tracking', paid_on: null, remaining_cents: 100 }, 'Paga (antes do registro)'],
    [{ status: 'closed', paid_on: null, remaining_cents: 100 }, 'Fechada'],
    [{ status: 'open', paid_on: null, remaining_cents: 100 }, 'Aberta'],
    [{ status: 'future', paid_on: null, remaining_cents: 0 }, 'Futura'],
  ] as const)('%o → %s', (invoice, expected) => {
    expect(plain(invoiceStatusText(invoice))).toBe(expected)
  })
})
