import { formatDate } from '@/lib/dates'
import { bankName } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import type { InvoiceImport, InvoiceImportDetail } from '@/lib/types'

export const isStatement = (item: InvoiceImport) => item.source === 'account_statement'

/** "Extrato Nubank" ou "Fatura <cartão>". */
export function importName(item: InvoiceImport, cardName?: string): string {
  return isStatement(item) ? `Extrato ${bankName(item.bank)}` : `Fatura ${cardName ?? 'Cartão'}`
}

/** O período do extrato ou o vencimento da fatura. */
export function importHeading(item: InvoiceImport): string {
  if (isStatement(item) && item.period_start && item.period_end) {
    return `${formatDate(item.period_start)} a ${formatDate(item.period_end)}`
  }
  return item.due_date ? `Vence ${formatDate(item.due_date)}` : ''
}

export function importDescription(detail: InvoiceImportDetail): string {
  if (!isStatement(detail)) return `${importHeading(detail)} · total ${formatCents(detail.total_cents)}`
  const income = detail.lines.filter((line) => line.is_credit).reduce((sum, line) => sum + line.amount_cents, 0)
  return `${importHeading(detail)} · entradas ${formatCents(income)} · saídas ${formatCents(detail.total_cents)}`
}
