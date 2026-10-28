import type { ReactNode } from 'react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCents } from '@/lib/money'
import { cn } from '@/lib/utils'

/** Exibição de valores: quantias, cartões de total e barras de progresso que mostram estouro. */

export function Amount({ cents, kind, className }: { cents: number; kind?: 'income' | 'expense'; className?: string }) {
  return (
    <span className={cn('tabular-nums', kind === 'income' && 'text-income', className)}>
      {kind === 'income' ? '+ ' : ''}
      {formatCents(cents)}
    </span>
  )
}

interface StatCardProps {
  title: string
  cents: number
  hint?: ReactNode
  tone?: 'income' | 'expense' | 'savings' | 'neutral'
}

export function StatCard({ title, cents, hint, tone = 'neutral' }: StatCardProps) {
  const toneClass = {
    income: 'text-income',
    expense: 'text-foreground',
    savings: 'text-savings',
    neutral: cents < 0 ? 'text-destructive' : 'text-foreground',
  }[tone]
  return (
    <Card>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className={cn('text-2xl tabular-nums', toneClass)}>{formatCents(cents)}</CardTitle>
      </CardHeader>
      {hint && <CardContent className="text-xs text-muted-foreground">{hint}</CardContent>}
    </Card>
  )
}

interface ProgressBarProps {
  label: string
  value: number
  max: number
  tone: 'needs' | 'wants' | 'savings' | 'income' | 'neutral'
  /** Passar do máximo é ruim (gasto) ou bom (poupança)? */
  overflowIsBad?: boolean
  detail?: ReactNode
}

/** Barra que mostra quando passa de 100%, coisa que a rosca da planilha não conseguia mostrar. */
export function ProgressBar({ label, value, max, tone, overflowIsBad = true, detail }: ProgressBarProps) {
  const pct = max > 0 ? (value / max) * 100 : value > 0 ? Infinity : 0
  const over = pct > 100
  const fill = {
    needs: 'bg-needs',
    wants: 'bg-wants',
    savings: 'bg-savings',
    income: 'bg-income',
    neutral: 'bg-primary',
  }[tone]
  const pctText = Number.isFinite(pct) ? `${pct.toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%` : 'sem limite'
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">{label}</span>
        <span
          className={cn(
            'tabular-nums text-xs',
            over && overflowIsBad ? 'font-semibold text-destructive' : 'text-muted-foreground',
          )}
        >
          {pctText}
        </span>
      </div>
      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Number.isFinite(pct) ? Math.round(Math.min(pct, 100)) : 100}
        aria-valuetext={pctText}
      >
        <div
          className={cn('h-full rounded-full transition-all', over && overflowIsBad ? 'bg-destructive' : fill)}
          style={{ width: `${Math.min(Number.isFinite(pct) ? pct : 100, 100)}%` }}
        />
      </div>
      {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
    </div>
  )
}
