import { describe, expect, it } from 'vitest'

import { groupIdentified, groupPending, skippedLines } from './invoice-groups'
import { category, line } from './test-data'

describe('agrupamentos da fatura', () => {
  it('agrupa pendentes por estabelecimento e soma, maior total primeiro', () => {
    const groups = groupPending([
      line({ id: 1, merchant_key: 'LOJA', description: 'Loja', amount_cents: 1000 }),
      line({ id: 2, merchant_key: 'LOJA', description: 'Loja', amount_cents: 500 }),
      line({ id: 3, merchant_key: 'OUTRA', description: 'Outra', amount_cents: 2000 }),
      line({ id: 4, merchant_key: 'LOJA', status: 'identified', category_id: 10 }),
    ])
    expect(groups.map((group) => [group.merchantKey, group.description, group.lines.length, group.totalCents])).toEqual(
      [
        ['OUTRA', 'Outra', 1, 2000],
        ['LOJA', 'Loja', 2, 1500],
      ],
    )
  })

  it('agrupa identificados e importados por categoria, maior total primeiro', () => {
    const categories = [category({ id: 10, name: 'Lazer' }), category({ id: 11, name: 'Transporte' })]
    const groups = groupIdentified(
      [
        line({ id: 1, status: 'identified', category_id: 10, amount_cents: 300 }),
        line({ id: 2, status: 'imported', category_id: 11, amount_cents: 900 }),
        line({ id: 3, status: 'identified', category_id: 10, amount_cents: 100 }),
        line({ id: 4, status: 'pending' }),
      ],
      categories,
    )
    expect(groups.map((group) => [group.category.name, group.lines.length, group.totalCents])).toEqual([
      ['Transporte', 1, 900],
      ['Lazer', 2, 400],
    ])
  })

  it('separa as linhas fora da importação', () => {
    const lines = [line({ id: 1, status: 'skipped', skip_reason: 'payment' }), line({ id: 2 })]
    expect(skippedLines(lines).map((item) => item.id)).toEqual([1])
  })
})
