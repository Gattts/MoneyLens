import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/dates'
import { SKIP_REASON_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import type { InvoiceLine } from '@/lib/types'

import { skippedLines } from './invoice-groups'

export function SkippedSection({ lines, onChanged }: { lines: InvoiceLine[]; onChanged: () => void }) {
  const skipped = skippedLines(lines)
  if (skipped.length === 0) return null

  async function include(line: InvoiceLine) {
    try {
      await api.invoiceLines.include(line.id)
      onChanged()
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : 'Não foi possível incluir.')
    }
  }

  return (
    <details className="rounded-xl border bg-card p-4">
      <summary className="cursor-pointer font-medium">Fora da importação ({skipped.length})</summary>
      <ul className="mt-3 flex flex-col gap-2">
        {skipped.map((line) => (
          <li key={line.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="min-w-0">
              <span className="block truncate">
                {formatDate(line.date)} · {line.description} · {formatCents(line.amount_cents)}
              </span>
              <span className="text-muted-foreground">{line.skip_reason && SKIP_REASON_LABELS[line.skip_reason]}</span>
            </span>
            {line.skip_reason === 'duplicate' && (
              <Button size="sm" variant="outline" onClick={() => void include(line)}>
                Importar mesmo assim
              </Button>
            )}
          </li>
        ))}
      </ul>
    </details>
  )
}
