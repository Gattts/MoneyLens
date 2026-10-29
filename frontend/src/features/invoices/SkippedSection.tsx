import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { api } from '@/lib/api'
import { formatDate, formatDayMonth } from '@/lib/dates'
import { SKIP_REASON_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import type { Card, InvoiceImportDetail, InvoiceLine } from '@/lib/types'

import { CardPaymentActions } from './CardPaymentActions'
import { skippedLines } from './invoice-groups'

const INCLUDE_LABELS: Partial<Record<NonNullable<InvoiceLine['skip_reason']>, string>> = {
  duplicate: 'Importar mesmo assim',
  already_imported: 'Importar mesmo assim',
  ignored: 'Voltar para o standby',
}

function reasonText(line: InvoiceLine): string | null {
  if (line.payment_id !== null) {
    return line.skip_reason === 'payment'
      ? 'Pagamento da fatura anterior (registrado)'
      : 'Pagamento de fatura (registrado)'
  }
  if (line.skip_reason === 'card_payment') {
    const suggestion = line.payment_suggestion
    return suggestion
      ? `Parece o pagamento da fatura ${suggestion.card_name} (venc. ${formatDayMonth(suggestion.due_date)})`
      : 'Pagamento de fatura: escolha o cartão e a fatura'
  }
  if (line.duplicate_of) return `Parece a fixa ${line.duplicate_of}: confirme a fixa no Painel.`
  return line.skip_reason && SKIP_REASON_LABELS[line.skip_reason]
}

export function SkippedSection({
  lines,
  cards = [],
  investment = null,
  onChanged,
}: {
  lines: InvoiceLine[]
  cards?: Card[]
  investment?: InvoiceImportDetail['investment']
  onChanged: () => void
}) {
  const including = useSingleFlight()
  const skipped = skippedLines(lines)
  if (skipped.length === 0) return null

  function include(line: InvoiceLine) {
    void including.run(async () => {
      try {
        await api.invoiceLines.include(line.id)
        onChanged()
      } catch (failure) {
        toast.error(failure instanceof Error ? failure.message : 'Não foi possível incluir.')
      }
    })
  }

  return (
    <details className="rounded-xl border bg-card p-4">
      <summary className="cursor-pointer font-medium">Fora da importação ({skipped.length})</summary>
      {investment && (investment.applied_cents > 0 || investment.redeemed_cents > 0) && (
        <p className="mt-3 text-sm">
          Aplicou {formatCents(investment.applied_cents)}, resgatou {formatCents(investment.redeemed_cents)}.
        </p>
      )}
      <ul className="mt-3 flex flex-col gap-2">
        {skipped.map((line) => {
          const includeLabel = line.skip_reason ? INCLUDE_LABELS[line.skip_reason] : undefined
          return (
            <li key={line.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="min-w-0">
                <span className="block truncate">
                  {formatDate(line.date)} · {line.description} · {formatCents(line.amount_cents)}
                </span>
                <span className="text-muted-foreground">{reasonText(line)}</span>
              </span>
              {line.skip_reason === 'card_payment' && line.payment_id === null && (
                <CardPaymentActions line={line} cards={cards} onChanged={onChanged} />
              )}
              {includeLabel && (
                <Button size="sm" variant="outline" disabled={including.pending} onClick={() => include(line)}>
                  {includeLabel}
                </Button>
              )}
            </li>
          )
        })}
      </ul>
    </details>
  )
}
