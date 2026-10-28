import { toast } from 'sonner'

import { LoadingBlock, QueryError } from '@/components/query-state'
import { FormDialog } from '@/components/FormDialog'
import { api } from '@/lib/api'
import { currentMonth, todayIso } from '@/lib/dates'
import { useCards, useCategories, useGoals, useRefreshData } from '@/lib/queries'
import type { Transaction, TransactionCreate } from '@/lib/types'

import { TransactionForm } from './TransactionForm'

interface TransactionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  transaction?: Transaction
  /** Mês aberto na tela: um lançamento novo começa com a data de hoje ou com o 1º dia desse mês. */
  month: string
}

export function TransactionDialog({ open, onOpenChange, transaction, month }: TransactionDialogProps) {
  const categories = useCategories(open)
  const cards = useCards(open)
  const goals = useGoals(open)
  const refresh = useRefreshData()
  const defaultDate = month === currentMonth() ? todayIso() : `${month}-01`

  async function save(payload: TransactionCreate) {
    if (transaction) {
      await api.transactions.update(transaction.id, payload)
      toast.success('Lançamento atualizado.')
    } else {
      const created = await api.transactions.create(payload)
      toast.success(created.length > 1 ? `Compra lançada em ${created.length} parcelas.` : 'Lançamento salvo.')
    }
    void refresh()
    onOpenChange(false)
  }

  const error = categories.error ?? cards.error ?? goals.error
  return (
    <FormDialog open={open} onOpenChange={onOpenChange} title={transaction ? 'Editar lançamento' : 'Novo lançamento'}>
      {error ? (
        <QueryError error={error} />
      ) : !categories.data || !cards.data || !goals.data ? (
        <LoadingBlock rows={5} />
      ) : (
        <TransactionForm
          key={transaction?.id ?? 'novo'}
          categories={categories.data}
          cards={cards.data}
          goals={goals.data}
          initial={transaction}
          defaultDate={defaultDate}
          onSubmit={save}
          onCancel={() => onOpenChange(false)}
        />
      )}
    </FormDialog>
  )
}
