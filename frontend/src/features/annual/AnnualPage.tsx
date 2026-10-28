import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts'

import { StatCard } from '@/components/money-display'
import { PageHeader, SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Button } from '@/components/ui/button'
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useYearParam } from '@/hooks/usePeriodParams'
import { formatMonthLabel, formatMonthShort } from '@/lib/dates'
import { THERMOMETER_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import { useYearSummary } from '@/lib/queries'
import type { PeriodTotals, YearMonth } from '@/lib/types'
import { cn } from '@/lib/utils'

const chartConfig = {
  income: { label: 'Receitas', color: 'var(--income)' },
  spending: { label: 'Gastos', color: 'var(--expense)' },
  savings: { label: 'Poupança', color: 'var(--savings)' },
} satisfies ChartConfig

const compact = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 })

const hasPending = (period: PeriodTotals) =>
  [period.income, period.needs, period.wants, period.savings].some((flow) => flow.pending_cents > 0)

function MonthRow({ month }: { month: YearMonth }) {
  const pending = hasPending(month)
  const label = formatMonthLabel(month.month).split(' de ')[0]
  return (
    <TableRow className={cn(pending && 'text-muted-foreground')}>
      <TableCell className="capitalize">
        {label}
        {pending && <span title="Inclui fixas ainda não confirmadas"> *</span>}
      </TableCell>
      <TableCell className="text-right tabular-nums">{formatCents(month.income.total_cents)}</TableCell>
      <TableCell className="text-right tabular-nums">{formatCents(month.needs.total_cents)}</TableCell>
      <TableCell className="text-right tabular-nums">{formatCents(month.wants.total_cents)}</TableCell>
      <TableCell className="text-right tabular-nums">{formatCents(month.savings.total_cents)}</TableCell>
      <TableCell className={cn('text-right font-medium tabular-nums', month.balance_cents < 0 && 'text-destructive')}>
        {formatCents(month.balance_cents)}
      </TableCell>
    </TableRow>
  )
}

export function AnnualPage() {
  const [year, setYear] = useYearParam()
  const summary = useYearSummary(year)

  return (
    <>
      <PageHeader
        title="Balanço anual"
        description="O ano mês a mês. Linhas com * ainda têm fixas a confirmar."
        actions={
          <div className="flex items-center gap-1" role="group" aria-label="Escolher ano">
            <Button
              variant="outline"
              size="icon"
              aria-label="Ano anterior"
              disabled={year <= 2000}
              onClick={() => setYear(year - 1)}
            >
              <ChevronLeftIcon />
            </Button>
            <span className="min-w-16 text-center text-sm font-medium" aria-live="polite">
              {year}
            </span>
            <Button
              variant="outline"
              size="icon"
              aria-label="Próximo ano"
              disabled={year >= 2100}
              onClick={() => setYear(year + 1)}
            >
              <ChevronRightIcon />
            </Button>
          </div>
        }
      />
      {summary.isError ? (
        <QueryError error={summary.error} onRetry={() => void summary.refetch()} />
      ) : summary.isPending ? (
        <LoadingBlock rows={8} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard title="Receitas no ano" cents={summary.data.income.total_cents} tone="income" />
            <StatCard
              title="Gastos no ano"
              cents={summary.data.needs.total_cents + summary.data.wants.total_cents}
              tone="expense"
              hint={`Termômetro do ano: ${THERMOMETER_LABELS[summary.data.thermometer.status]}`}
            />
            <StatCard title="Poupança no ano" cents={summary.data.savings.total_cents} tone="savings" />
            <StatCard title="Saldo do ano" cents={summary.data.balance_cents} />
          </div>

          <SectionCard title="Receitas, gastos e poupança por mês">
            <ChartContainer config={chartConfig} className="h-72 w-full">
              <BarChart
                accessibilityLayer
                data={summary.data.months.map((month) => ({
                  label: formatMonthShort(month.month).split('/')[0],
                  income: month.income.total_cents / 100,
                  spending: (month.needs.total_cents + month.wants.total_cents) / 100,
                  savings: month.savings.total_cents / 100,
                }))}
              >
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} />
                <YAxis
                  width={56}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value: number) => compact.format(value)}
                />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value, name) => (
                        <div className="flex w-full justify-between gap-4">
                          <span className="text-muted-foreground">
                            {chartConfig[name as keyof typeof chartConfig]?.label ?? name}
                          </span>
                          <span className="font-medium tabular-nums">
                            {formatCents(Math.round(Number(value) * 100))}
                          </span>
                        </div>
                      )}
                    />
                  }
                />
                <ChartLegend content={<ChartLegendContent />} />
                <Bar dataKey="income" fill="var(--color-income)" radius={4} />
                <Bar dataKey="spending" fill="var(--color-spending)" radius={4} />
                <Bar dataKey="savings" fill="var(--color-savings)" radius={4} />
              </BarChart>
            </ChartContainer>
          </SectionCard>

          <SectionCard title="Mês a mês">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Mês</TableHead>
                  <TableHead className="text-right">Receitas</TableHead>
                  <TableHead className="text-right">Necessidades</TableHead>
                  <TableHead className="text-right">Desejos</TableHead>
                  <TableHead className="text-right">Poupança</TableHead>
                  <TableHead className="text-right">Saldo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.data.months.map((month) => (
                  <MonthRow key={month.month} month={month} />
                ))}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell>Total</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatCents(summary.data.income.total_cents)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatCents(summary.data.needs.total_cents)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatCents(summary.data.wants.total_cents)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatCents(summary.data.savings.total_cents)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatCents(summary.data.balance_cents)}</TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </SectionCard>
        </>
      )}
    </>
  )
}
