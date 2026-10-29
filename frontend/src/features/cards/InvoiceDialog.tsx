import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { useState } from 'react'

import { Amount } from '@/components/money-display'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { FormDialog } from '@/components/FormDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { addMonths, formatDate, formatMonthLabel } from '@/lib/dates'
import { toast } from 'sonner'

import { useSingleFlight } from '@/hooks/useSingleFlight'
import { api } from '@/lib/api'
import { PAYMENT_SOURCE_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import { useInvoice, useRefreshData } from '@/lib/queries'
import type { Card, CardPayment, Invoice, InvoiceStatus } from '@/lib/types'

import { invoiceStatusText } from './invoice-status'
import { PaymentForm } from './PaymentForm'

const PAYABLE: InvoiceStatus[] = ['closed', 'overdue', 'partially_paid']

function PaymentsSection({ cardId, invoice }: { cardId: number; invoice: Invoice }) {
  const refresh = useRefreshData()
  const removing = useSingleFlight()
  const [paying, setPaying] = useState(false)

  function remove(payment: CardPayment) {
    void removing.run(async () => {
      try {
        await api.cardPayments.remove(payment.id)
        toast.success('Pagamento excluído.')
        void refresh()
      } catch (failure) {
        toast.error(failure instanceof Error ? failure.message : 'Não foi possível excluir.')
      }
    })
  }

  return (
    <div className="flex flex-col gap-2">
      {invoice.payments.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {invoice.payments.map((payment) => (
            <li key={payment.id} className="flex items-center justify-between gap-2">
              <span>
                Pago em {formatDate(payment.paid_on)} · {formatCents(payment.amount_cents)} ·{' '}
                {PAYMENT_SOURCE_LABELS[payment.source]}
              </span>
              {payment.source !== 'card_invoice' && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={removing.pending}
                  aria-label={`Excluir pagamento de ${formatDate(payment.paid_on)}`}
                  onClick={() => remove(payment)}
                >
                  Excluir
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
      {PAYABLE.includes(invoice.status) &&
        (paying ? (
          <PaymentForm
            cardId={cardId}
            month={invoice.month}
            remainingCents={invoice.remaining_cents}
            onDone={() => setPaying(false)}
          />
        ) : (
          <Button variant="outline" size="sm" className="self-start" onClick={() => setPaying(true)}>
            Marcar como paga
          </Button>
        ))}
    </div>
  )
}

export function InvoiceDialog({ card, onClose }: { card: Card; onClose: () => void }) {
  const [month, setMonth] = useState(card.current_invoice.month)
  const invoice = useInvoice(card.id, month)

  return (
    <FormDialog open onOpenChange={(open) => !open && onClose()} title={`Fatura ${card.name}`}>
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="outline"
          size="icon"
          aria-label="Fatura anterior"
          onClick={() => setMonth(addMonths(month, -1))}
        >
          <ChevronLeftIcon />
        </Button>
        <span className="text-sm font-medium" aria-live="polite">
          Fatura de {formatMonthLabel(month)}
        </span>
        <Button variant="outline" size="icon" aria-label="Próxima fatura" onClick={() => setMonth(addMonths(month, 1))}>
          <ChevronRightIcon />
        </Button>
      </div>
      {invoice.isError ? (
        <QueryError error={invoice.error} onRetry={() => void invoice.refetch()} />
      ) : !invoice.data ? (
        <LoadingBlock rows={4} />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 rounded-lg border p-3 text-sm">
            <div>
              <p className="text-muted-foreground">Total</p>
              <p className="text-lg font-semibold tabular-nums">{formatCents(invoice.data.total_cents)}</p>
            </div>
            <div className="text-right">
              <Badge variant="outline">{invoiceStatusText(invoice.data)}</Badge>
            </div>
            <p className="text-muted-foreground">Fecha em {formatDate(invoice.data.closing_date)}</p>
            <p className="text-right text-muted-foreground">Vence em {formatDate(invoice.data.due_date)}</p>
            <p className="col-span-2 text-xs text-muted-foreground">
              Compras de {formatDate(invoice.data.period_start)} a {formatDate(invoice.data.period_end)}.
            </p>
          </div>
          <PaymentsSection key={invoice.data.month} cardId={card.id} invoice={invoice.data} />
          {invoice.data.transactions.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma compra nesta fatura.</p>
          ) : (
            <ul className="flex flex-col divide-y">
              {invoice.data.transactions.map((purchase) => (
                <li key={purchase.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">
                      {purchase.description}
                      {purchase.installment_total && (
                        <Badge variant="outline" className="ml-2">
                          {purchase.installment_number}/{purchase.installment_total}
                        </Badge>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">{formatDate(purchase.date)}</p>
                  </div>
                  <Amount cents={purchase.amount_cents} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </FormDialog>
  )
}
