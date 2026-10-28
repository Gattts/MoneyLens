import { useMutation } from '@tanstack/react-query'
import { CheckIcon, PlusIcon } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { Amount, ProgressBar, StatCard } from '@/components/money-display'
import { MonthPicker, PageHeader, SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TransactionDialog } from '@/features/transactions/TransactionDialog'
import { useMonthParam } from '@/hooks/usePeriodParams'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/dates'
import { BUCKET_LABELS, INVOICE_STATUS_LABELS, THERMOMETER_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import { useCards, useInvoiceImports, useMonthSummary, useRefreshData } from '@/lib/queries'
import type { MonthSummary, PendingOccurrence, Thermometer } from '@/lib/types'
import { cn } from '@/lib/utils'

const THERMOMETER_STYLES: Record<Thermometer['status'], string> = {
  no_data: 'bg-muted text-muted-foreground',
  controlled: 'bg-income/15 text-income',
  warning: 'bg-wants/20 text-amber-700 dark:text-wants',
  negative: 'bg-destructive/15 text-destructive',
}

function thermometerText({ status, spending_pct, limit_pct }: Thermometer): string {
  if (status === 'no_data') return 'Lance receitas e gastos para ver como o mês está.'
  if (spending_pct === null) return 'Há gastos, mas nenhuma receita prevista neste mês.'
  const pct = spending_pct.toLocaleString('pt-BR')
  return `Necessidades e desejos somam ${pct}% da renda prevista. Seu plano é gastar até ${limit_pct}%.`
}

function pendingHint(pendingCents: number) {
  return pendingCents > 0 ? `${formatCents(pendingCents)} ainda previsto (fixas a confirmar)` : 'Tudo confirmado'
}

function Overview({ summary }: { summary: MonthSummary }) {
  const spending = summary.needs.total_cents + summary.wants.total_cents
  const spendingPending = summary.needs.pending_cents + summary.wants.pending_cents
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        title="Receitas"
        cents={summary.income.total_cents}
        tone="income"
        hint={pendingHint(summary.income.pending_cents)}
      />
      <StatCard title="Gastos" cents={spending} tone="expense" hint={pendingHint(spendingPending)} />
      <StatCard
        title="Poupança"
        cents={summary.savings.total_cents}
        tone="savings"
        hint={pendingHint(summary.savings.pending_cents)}
      />
      <StatCard
        title="Saldo previsto"
        cents={summary.balance_cents}
        hint={`Realizado até agora: ${formatCents(summary.realized_balance_cents)}`}
      />
    </div>
  )
}

function BudgetSection({ summary }: { summary: MonthSummary }) {
  const thermometer = summary.thermometer
  return (
    <SectionCard
      title="Orçamento do mês"
      description="Quanto de cada grupo já foi usado, considerando as fixas previstas."
    >
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3">
          <span className={cn('rounded-md px-2.5 py-1 text-sm font-semibold', THERMOMETER_STYLES[thermometer.status])}>
            {THERMOMETER_LABELS[thermometer.status]}
          </span>
          <p className="text-sm text-muted-foreground">{thermometerText(thermometer)}</p>
        </div>
        {summary.income.total_cents === 0 ? (
          <p className="text-sm text-muted-foreground">
            Sem receita prevista neste mês, não há como dividir o orçamento.{' '}
            <Link to="/fixas" className="font-medium text-foreground underline underline-offset-4">
              Cadastre seu salário como fixa
            </Link>{' '}
            ou lance uma receita.
          </p>
        ) : (
          summary.budget.map((line) => (
            <ProgressBar
              key={line.bucket}
              label={`${BUCKET_LABELS[line.bucket]} (${line.percent}% da renda)`}
              value={line.used_cents}
              max={line.planned_cents}
              tone={line.bucket}
              overflowIsBad={line.bucket !== 'savings'}
              detail={
                <>
                  {formatCents(line.used_cents)} de {formatCents(line.planned_cents)} ·{' '}
                  {line.remaining_cents >= 0
                    ? `${line.bucket === 'savings' ? 'faltam' : 'sobram'} ${formatCents(line.remaining_cents)}`
                    : `${line.bucket === 'savings' ? 'passou da meta em' : 'estourou em'} ${formatCents(-line.remaining_cents)}`}
                </>
              }
            />
          ))
        )}
      </div>
    </SectionCard>
  )
}

function PendingSection({ month, pending }: { month: string; pending: PendingOccurrence[] }) {
  const refresh = useRefreshData()
  const confirm = useMutation({
    mutationFn: (occurrence: PendingOccurrence) => api.recurring.confirm(occurrence.rule_id, { month }),
    onSuccess: (_transaction, occurrence) => {
      toast.success(`“${occurrence.description}” confirmada.`)
      void refresh()
    },
    onError: (error) => toast.error(error.message),
    onSettled: (_result, _error, occurrence) => inFlight.current.delete(occurrence.rule_id),
  })
  // O `disabled` só chega na próxima renderização; num clique duplo, o 2º clique viria antes dele.
  const inFlight = useRef(new Set<number>())

  function confirmOnce(occurrence: PendingOccurrence) {
    if (inFlight.current.has(occurrence.rule_id)) return
    inFlight.current.add(occurrence.rule_id)
    confirm.mutate(occurrence)
  }

  return (
    <SectionCard title="Fixas a confirmar" description="Entram como previstas; confirme quando pagar ou receber.">
      {pending.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma fixa pendente neste mês.</p>
      ) : (
        <ul className="flex flex-col divide-y">
          {pending.map((occurrence) => (
            <li key={occurrence.rule_id} className="flex items-center justify-between gap-3 py-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{occurrence.description}</p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(occurrence.date)} · <Amount cents={occurrence.amount_cents} kind={occurrence.kind} />
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                disabled={confirm.isPending}
                aria-label={`Confirmar ${occurrence.description}`}
                onClick={() => confirmOnce(occurrence)}
              >
                <CheckIcon /> Confirmar
              </Button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}

function CategoriesSection({ summary }: { summary: MonthSummary }) {
  const top = summary.by_category.slice(0, 8)
  const largest = top[0]?.total_cents ?? 0
  return (
    <SectionCard
      title="Para onde foi o dinheiro"
      description="Despesas do mês por categoria, incluindo fixas previstas."
    >
      {top.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma despesa neste mês.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {top.map((category) => (
            <ProgressBar
              key={category.category_id}
              label={`${category.icon} ${category.name}`.trim()}
              value={category.total_cents}
              max={largest}
              tone="neutral"
              overflowIsBad={false}
              detail={formatCents(category.total_cents)}
            />
          ))}
        </div>
      )}
    </SectionCard>
  )
}

function CardsSection() {
  const cards = useCards()
  const active = cards.data?.filter((card) => !card.archived) ?? []
  return (
    <SectionCard
      title="Cartões"
      description="Fatura atual e limite usado (inclui parcelas futuras)."
      action={
        <Button asChild variant="ghost" size="sm">
          <Link to="/cartoes">Ver cartões</Link>
        </Button>
      }
    >
      {cards.isError ? (
        <QueryError error={cards.error} onRetry={() => void cards.refetch()} />
      ) : cards.isPending ? (
        <LoadingBlock rows={2} />
      ) : active.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhum cartão cadastrado.</p>
      ) : (
        <div className="flex flex-col gap-5">
          {active.map((card) => (
            <div key={card.id} className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="font-medium">{card.name}</span>
                <span className="flex items-center gap-2">
                  <span className="tabular-nums">{formatCents(card.current_invoice.total_cents)}</span>
                  <Badge variant="outline">{INVOICE_STATUS_LABELS[card.current_invoice.status]}</Badge>
                </span>
              </div>
              <ProgressBar
                label="Limite usado"
                value={card.used_cents}
                max={card.limit_cents}
                tone="neutral"
                detail={`Vence em ${formatDate(card.current_invoice.due_date)} · disponível ${formatCents(card.available_cents)}`}
              />
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  )
}

/** Aviso das compras de faturas que ainda esperam categoria (some quando não há nenhuma). */
function StandbyNotice() {
  const imports = useInvoiceImports()
  if (!imports.data || imports.data.standby_count === 0) return null
  const { standby_count: count, standby_cents: cents } = imports.data
  return (
    <SectionCard title="Faturas com gastos em standby">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>
          {count} gasto(s) em standby ({formatCents(cents)})
        </span>
        <Button asChild size="sm" variant="outline">
          <Link to="/faturas">Resolver</Link>
        </Button>
      </div>
    </SectionCard>
  )
}

export function DashboardPage() {
  const [month, setMonth] = useMonthParam()
  const summary = useMonthSummary(month)
  const [creating, setCreating] = useState(false)

  return (
    <>
      <PageHeader
        title="Painel"
        description="Como está o mês, com o que já aconteceu e o que ainda está previsto."
        actions={
          <>
            <MonthPicker month={month} onChange={setMonth} />
            <Button onClick={() => setCreating(true)}>
              <PlusIcon /> Novo lançamento
            </Button>
          </>
        }
      />
      {summary.isError ? (
        <QueryError error={summary.error} onRetry={() => void summary.refetch()} />
      ) : summary.isPending ? (
        <LoadingBlock rows={6} />
      ) : (
        <>
          <Overview summary={summary.data} />
          <StandbyNotice />
          <div className="grid gap-4 lg:grid-cols-2">
            <BudgetSection summary={summary.data} />
            <PendingSection month={month} pending={summary.data.pending} />
            <CategoriesSection summary={summary.data} />
            <CardsSection />
          </div>
        </>
      )}
      <TransactionDialog open={creating} onOpenChange={setCreating} month={month} />
    </>
  )
}
