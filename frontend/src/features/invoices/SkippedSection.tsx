import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/dates'
import { SKIP_REASON_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import type { InvoiceImportDetail, InvoiceLine } from '@/lib/types'

import { skippedLines } from './invoice-groups'

const INCLUDE_LABELS: Partial<Record<NonNullable<InvoiceLine['skip_reason']>, string>> = {
  duplicate: 'Importar mesmo assim',
  already_imported: 'Importar mesmo assim',
  ignored: 'Voltar para o standby',
}

export function SkippedSection({
  lines,
  investment = null,
  onChanged,
}: {
  lines: InvoiceLine[]
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
                <span className="text-muted-foreground">
                  {line.duplicate_of
                    ? `Parece a fixa ${line.duplicate_of}: confirme a fixa no Painel.`
                    : line.skip_reason && SKIP_REASON_LABELS[line.skip_reason]}
                </span>
              </span>
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
