import { useMutation } from '@tanstack/react-query'
import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { MonthPicker, PageHeader } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { ConfirmDialog, type ConfirmAction } from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useMonthParam } from '@/hooks/usePeriodParams'
import { api } from '@/lib/api'
import { formatDate, formatMonthLabel } from '@/lib/dates'
import { formatCents } from '@/lib/money'
import { useCards, useCategories, useGoals, useRefreshData, useTransactions } from '@/lib/queries'
import type { Transaction } from '@/lib/types'

import { TransactionDialog } from './TransactionDialog'
import { type FilterValues, TransactionFilters } from './TransactionFilters'
import { TransactionsTable } from './TransactionsTable'

type DeleteScope = 'one' | 'installments'

function describeForDeletion(transaction: Transaction) {
  const lines = [
    `“${transaction.description}” de ${formatCents(transaction.amount_cents)} em ${formatDate(transaction.date)}.`,
  ]
  if (transaction.installment_total) lines.push(`Esta compra foi parcelada em ${transaction.installment_total}×.`)
  if (transaction.recurring_rule_id) lines.push('A fixa volta a aparecer como pendente neste mês.')
  return lines.join(' ')
}

export function TransactionsPage() {
  const [month, setMonth] = useMonthParam()
  const [filters, setFilters] = useState<FilterValues>({ search: '', kind: '', categoryId: '' })
  const query = useDebouncedValue(filters.search.trim())
  const transactions = useTransactions({
    month,
    q: query || undefined,
    kind: filters.kind || undefined,
    category_id: filters.categoryId ? Number(filters.categoryId) : undefined,
  })
  const categories = useCategories()
  const cards = useCards()
  const goals = useGoals()
  const refresh = useRefreshData()

  const [editing, setEditing] = useState<Transaction | undefined>()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleting, setDeleting] = useState<Transaction | null>(null)
  const remove = useMutation({
    mutationFn: ({ id, scope }: { id: number; scope: DeleteScope }) => api.transactions.remove(id, scope),
    onSuccess: () => {
      toast.success('Lançamento excluído.')
      setDeleting(null)
      void refresh()
    },
    onError: (error) => toast.error(error.message),
  })

  const rows = transactions.data ?? []
  const filtering = Boolean(query || filters.kind || filters.categoryId)

  function openDialog(transaction?: Transaction) {
    setEditing(transaction)
    setDialogOpen(true)
  }

  function deleteActions(transaction: Transaction): ConfirmAction[] {
    // A Promise faz o ConfirmDialog travar até o fim; o erro já vira aviso no onError.
    const removeWith = (scope: DeleteScope) => () =>
      remove.mutateAsync({ id: transaction.id, scope }).catch(() => undefined)
    if (!transaction.installment_total) return [{ label: 'Excluir', destructive: true, onConfirm: removeWith('one') }]
    return [
      { label: 'Só esta parcela', onConfirm: removeWith('one') },
      { label: 'Todas as parcelas', destructive: true, onConfirm: removeWith('installments') },
    ]
  }

  return (
    <>
      <PageHeader
        title="Lançamentos"
        description="Tudo o que entrou e saiu no mês."
        actions={
          <>
            <MonthPicker month={month} onChange={setMonth} />
            <Button onClick={() => openDialog()}>
              <PlusIcon /> Novo lançamento
            </Button>
          </>
        }
      />

      <TransactionFilters values={filters} categories={categories.data ?? []} onChange={setFilters} />

      {transactions.isError ? (
        <QueryError error={transactions.error} onRetry={() => void transactions.refetch()} />
      ) : transactions.isPending ? (
        <LoadingBlock rows={6} />
      ) : rows.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>
              {filtering ? 'Nada encontrado com esses filtros' : `Nenhum lançamento em ${formatMonthLabel(month)}`}
            </EmptyTitle>
            <EmptyDescription>
              {filtering ? 'Tente outra busca ou limpe os filtros.' : 'Registre o primeiro gasto ou receita do mês.'}
            </EmptyDescription>
          </EmptyHeader>
          {!filtering && (
            <Button onClick={() => openDialog()}>
              <PlusIcon /> Novo lançamento
            </Button>
          )}
        </Empty>
      ) : (
        <TransactionsTable
          rows={rows}
          categories={categories.data ?? []}
          cards={cards.data ?? []}
          goals={goals.data ?? []}
          onEdit={openDialog}
          onDelete={setDeleting}
        />
      )}

      <TransactionDialog open={dialogOpen} onOpenChange={setDialogOpen} transaction={editing} month={month} />

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Excluir lançamento?"
        description={deleting ? describeForDeletion(deleting) : ''}
        pending={remove.isPending}
        actions={deleting ? deleteActions(deleting) : []}
      />
    </>
  )
}
