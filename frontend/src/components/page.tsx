import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { addMonths, currentMonth, formatMonthLabel } from '@/lib/dates'

/** Estrutura das páginas: cabeçalho, seletor de mês e cartões de seção. */

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

function capitalize(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function MonthPicker({ month, onChange }: { month: string; onChange: (month: string) => void }) {
  const today = currentMonth()
  return (
    <div className="flex items-center gap-1" role="group" aria-label="Escolher mês">
      <Button variant="outline" size="icon" aria-label="Mês anterior" onClick={() => onChange(addMonths(month, -1))}>
        <ChevronLeftIcon />
      </Button>
      <span className="min-w-36 text-center text-sm font-medium" aria-live="polite">
        {capitalize(formatMonthLabel(month))}
      </span>
      <Button variant="outline" size="icon" aria-label="Próximo mês" onClick={() => onChange(addMonths(month, 1))}>
        <ChevronRightIcon />
      </Button>
      {month !== today && (
        <Button variant="ghost" size="sm" onClick={() => onChange(today)}>
          Mês atual
        </Button>
      )}
    </div>
  )
}

export function SectionCard({
  title,
  description,
  action,
  children,
}: {
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-2">
        <div className="flex flex-col gap-1">
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}
