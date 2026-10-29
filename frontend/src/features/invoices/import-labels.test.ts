import { describe, expect, it } from 'vitest'

import { importDescription, importHeading, importName } from './import-labels'
import { detail, line, statement } from './test-data'

// formatCents separa "R$" do valor com espaço não separável.
const plain = (text: string) => text.replace(/\u00a0/g, ' ')

const STATEMENT = statement({
  total_cents: 21250,
  lines: [
    line({ id: 1, is_credit: true, amount_cents: 150000 }),
    line({ id: 2, amount_cents: 1250 }),
    line({ id: 3, is_credit: true, amount_cents: 2700, status: 'skipped', skip_reason: 'investment' }),
  ],
})

describe('nomes da importação', () => {
  it('extrato aparece pelo banco e pelo período', () => {
    expect(importName(STATEMENT)).toBe('Extrato Nubank')
    expect(importHeading(STATEMENT)).toBe('01/10/2026 a 27/10/2026')
    expect(plain(importDescription(STATEMENT))).toBe(
      '01/10/2026 a 27/10/2026 · entradas R$ 1.527,00 · saídas R$ 212,50',
    )
  })

  it('fatura aparece pelo cartão e pelo vencimento', () => {
    const invoice = detail({})
    expect(importName(invoice, 'Inter')).toBe('Fatura Inter')
    expect(importName(invoice)).toBe('Fatura Cartão')
    expect(importHeading(invoice)).toBe('Vence 12/10/2026')
    expect(plain(importDescription(invoice))).toBe('Vence 12/10/2026 · total R$ 73,90')
  })
})
