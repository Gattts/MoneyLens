import type { Category, InvoiceLine } from '@/lib/types'

export interface CategoryGroup {
  category: Category
  lines: InvoiceLine[]
  totalCents: number
}

export interface MerchantGroup {
  merchantKey: string
  description: string
  lines: InvoiceLine[]
  totalCents: number
}

const total = (lines: InvoiceLine[]) => lines.reduce((sum, line) => sum + line.amount_cents, 0)
const largestFirst = (a: { totalCents: number }, b: { totalCents: number }) => b.totalCents - a.totalCents

function groupBy<K>(lines: InvoiceLine[], key: (line: InvoiceLine) => K): Map<K, InvoiceLine[]> {
  const groups = new Map<K, InvoiceLine[]>()
  for (const line of lines) groups.set(key(line), [...(groups.get(key(line)) ?? []), line])
  return groups
}

/** Linhas reconhecidas (ainda não lançadas ou já lançadas), por categoria. */
export function groupIdentified(lines: InvoiceLine[], categories: Category[]): CategoryGroup[] {
  const recognized = lines.filter(
    (line) => (line.status === 'identified' || line.status === 'imported') && line.category_id !== null,
  )
  return [...groupBy(recognized, (line) => line.category_id)]
    .flatMap(([id, items]) => {
      const found = categories.find((candidate) => candidate.id === id)
      return found ? [{ category: found, lines: items, totalCents: total(items) }] : []
    })
    .sort(largestFirst)
}

/** Linhas em standby, por estabelecimento: resolver um grupo resolve todas as linhas dele. */
export function groupPending(lines: InvoiceLine[]): MerchantGroup[] {
  const pending = lines.filter((line) => line.status === 'pending')
  return [...groupBy(pending, (line) => line.merchant_key)]
    .map(([merchantKey, items]) => ({
      merchantKey,
      description: items[0].description,
      lines: items,
      totalCents: total(items),
    }))
    .sort(largestFirst)
}

export function skippedLines(lines: InvoiceLine[]): InvoiceLine[] {
  return lines.filter((line) => line.status === 'skipped')
}
