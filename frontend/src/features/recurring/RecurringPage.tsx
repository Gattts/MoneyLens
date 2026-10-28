import { PlusIcon } from 'lucide-react'
import { toast } from 'sonner'

import { Amount } from '@/components/money-display'
import { PageHeader } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormDialog } from '@/components/FormDialog'
import { RowActions } from '@/components/RowActions'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { paymentLabel } from '@/features/entries/entry-rules'
import { useEditor, useRemove } from '@/hooks/useCrud'
import { api } from '@/lib/api'
import { currentMonth, formatMonthShort } from '@/lib/dates'
import { useCards, useCategories, useRecurring, useRefreshData } from '@/lib/queries'
import type { RecurringInput, RecurringRule } from '@/lib/types'

import { RecurringForm } from './RecurringForm'

function period(rule: RecurringRule) {
  return `${formatMonthShort(rule.start_month)} → ${rule.end_month ? formatMonthShort(rule.end_month) : 'sem fim'}`
}

export function RecurringPage() {
  const rules = useRecurring()
  const categories = useCategories()
  const cards = useCards()
  const refresh = useRefreshData()
  const editor = useEditor<RecurringRule>()
  const removal = useRemove<RecurringRule>(api.recurring.remove, 'Fixa excluída.')
  const categoryById = new Map(categories.data?.map((category) => [category.id, category]))

  async function save(body: RecurringInput) {
    if (editor.item) await api.recurring.update(editor.item.id, body)
    else await api.recurring.create(body)
    toast.success(editor.item ? 'Fixa atualizada.' : 'Fixa criada.')
    void refresh()
    editor.setOpen(false)
  }

  const error = rules.error ?? categories.error ?? cards.error
  return (
    <>
      <PageHeader
        title="Fixas"
        description="Receitas e despesas que se repetem todo mês. Elas aparecem como previstas no painel até você confirmar."
        actions={
          <Button onClick={editor.create}>
            <PlusIcon /> Nova fixa
          </Button>
        }
      />
      {error ? (
        <QueryError error={error} onRetry={() => void rules.refetch()} />
      ) : !rules.data || !categories.data || !cards.data ? (
        <LoadingBlock rows={4} />
      ) : rules.data.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>Nenhuma fixa cadastrada</EmptyTitle>
            <EmptyDescription>
              Comece pelo salário e pelas contas de todo mês, como aluguel e internet.
            </EmptyDescription>
          </EmptyHeader>
          <Button onClick={editor.create}>
            <PlusIcon /> Nova fixa
          </Button>
        </Empty>
      ) : (
        <Card className="py-0">
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-14">Dia</TableHead>
                  <TableHead>Descrição</TableHead>
                  <TableHead className="hidden md:table-cell">Categoria</TableHead>
                  <TableHead className="hidden lg:table-cell">Período</TableHead>
                  <TableHead className="hidden lg:table-cell">Pagamento</TableHead>
                  <TableHead className="text-right">Valor</TableHead>
                  <TableHead className="w-20">
                    <span className="sr-only">Ações</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.data.map((rule) => {
                  const category = categoryById.get(rule.category_id)
                  return (
                    <TableRow key={rule.id}>
                      <TableCell className="tabular-nums">{rule.day_of_month}</TableCell>
                      <TableCell className="whitespace-normal">
                        <span className="font-medium">{rule.description}</span>
                        <span className="block text-xs text-muted-foreground lg:hidden">{period(rule)}</span>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {category ? `${category.icon} ${category.name}`.trim() : '—'}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">{period(rule)}</TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {paymentLabel(rule.payment_method, rule.card_id, cards.data)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Amount cents={rule.amount_cents} kind={rule.kind} />
                      </TableCell>
                      <TableCell>
                        <RowActions
                          label={rule.description}
                          onEdit={() => editor.edit(rule)}
                          onDelete={() => removal.ask(rule)}
                        />
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <FormDialog open={editor.open} onOpenChange={editor.setOpen} title={editor.item ? 'Editar fixa' : 'Nova fixa'}>
        {categories.data && cards.data && (
          <RecurringForm
            key={editor.item?.id ?? 'nova'}
            categories={categories.data}
            cards={cards.data}
            initial={editor.item}
            defaultMonth={currentMonth()}
            onSubmit={save}
            onCancel={() => editor.setOpen(false)}
          />
        )}
      </FormDialog>

      <ConfirmDialog
        open={removal.target !== null}
        onOpenChange={(open) => !open && removal.dismiss()}
        title={`Excluir “${removal.target?.description ?? ''}”?`}
        description="Os lançamentos já confirmados continuam no histórico; só deixam de aparecer as ocorrências futuras."
        pending={removal.pending}
        actions={[{ label: 'Excluir', destructive: true, onConfirm: removal.confirm }]}
      />
    </>
  )
}
