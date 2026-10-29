import { formatDayMonth } from '@/lib/dates'
import { INVOICE_STATUS_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import type { InvoiceSummary } from '@/lib/types'

/** "Paga em 05/11", "Paga em parte (faltam R$ 40,00)", "Vencida, sem pagamento"… */
export function invoiceStatusText(invoice: Pick<InvoiceSummary, 'status' | 'paid_on' | 'remaining_cents'>): string {
  if (invoice.status === 'paid' && invoice.paid_on) return `Paga em ${formatDayMonth(invoice.paid_on)}`
  if (invoice.status === 'partially_paid') return `Paga em parte (faltam ${formatCents(invoice.remaining_cents)})`
  return INVOICE_STATUS_LABELS[invoice.status]
}
