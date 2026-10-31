import { formatCents } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { SpendingLimit } from '@/lib/types'

const MARKS = [50, 90, 100]

/** Gasto sobre o teto, com as marcas de 50/90/100% e a marca da previsão do mês. */
export function LimitBar({ limit }: { limit: SpendingLimit }) {
  const width = Math.min(limit.percent, 100)
  const fill = limit.percent >= 100 ? 'bg-destructive' : limit.percent >= 90 ? 'bg-wants' : 'bg-primary'
  const forecast =
    limit.p50_cents === null || limit.amount_cents === 0
      ? null
      : Math.min((limit.p50_cents / limit.amount_cents) * 100, 100)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="tabular-nums">
          {formatCents(limit.spent_cents)} de {formatCents(limit.amount_cents)}
        </span>
        <span
          className={cn(
            'tabular-nums text-xs',
            limit.percent >= 100 ? 'font-semibold text-destructive' : 'text-muted-foreground',
          )}
        >
          {limit.percent}%
        </span>
      </div>
      <div className="relative h-2.5 w-full rounded-full bg-muted">
        <div className={cn('h-full rounded-full transition-all', fill)} style={{ width: `${width}%` }} />
        {MARKS.map((mark) => (
          <span
            key={mark}
            aria-hidden
            className="absolute top-0 h-full w-px bg-foreground/30"
            style={{ left: `calc(${mark}% - 1px)` }}
          />
        ))}
        {forecast !== null && limit.p50_cents !== null && (
          <span
            role="img"
            aria-label={`Previsão: ${formatCents(limit.p50_cents)}`}
            title={`Previsão do mês: ${formatCents(limit.p50_cents)}`}
            className="absolute -top-1 h-4.5 w-0.5 rounded bg-foreground"
            style={{ left: `calc(${forecast}% - 1px)` }}
          />
        )}
      </div>
    </div>
  )
}
