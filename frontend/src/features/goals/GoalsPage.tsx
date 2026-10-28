import { ArchiveIcon, ArchiveRestoreIcon, InfoIcon, PencilIcon, PlusIcon, Trash2Icon } from 'lucide-react'
import { toast } from 'sonner'

import { ProgressBar } from '@/components/money-display'
import { PageHeader } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormDialog } from '@/components/FormDialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { useEditor, useQuickAction, useRemove } from '@/hooks/useCrud'
import { api } from '@/lib/api'
import { formatMonthShort } from '@/lib/dates'
import { formatCents } from '@/lib/money'
import { useGoals, useRefreshData } from '@/lib/queries'
import type { Goal, GoalInput } from '@/lib/types'

import { GoalForm } from './GoalForm'

function toInput(goal: Goal): GoalInput {
  return {
    name: goal.name,
    icon: goal.icon,
    target_cents: goal.target_cents,
    target_date: goal.target_date,
    archived: goal.archived,
  }
}

function pace(goal: Goal): string | null {
  if (goal.remaining_cents === 0) return 'Meta alcançada! 🎉'
  if (goal.months_left === null || goal.monthly_needed_cents === null || !goal.target_date) return null
  if (goal.months_left === 0) return `A data-alvo (${formatMonthShort(goal.target_date)}) já passou.`
  const months = goal.months_left === 1 ? '1 mês' : `${goal.months_left} meses`
  return `Guarde ${formatCents(goal.monthly_needed_cents)} por mês até ${formatMonthShort(goal.target_date)} (${months}).`
}

export function GoalsPage() {
  const goals = useGoals()
  const refresh = useRefreshData()
  const editor = useEditor<Goal>()
  const removal = useRemove<Goal>(api.goals.remove, 'Meta excluída.')
  const archive = useQuickAction(
    (goal: Goal) => api.goals.update(goal.id, { ...toInput(goal), archived: !goal.archived }),
    (goal) => (goal.archived ? `“${goal.name}” voltou para a lista.` : `“${goal.name}” arquivada.`),
  )

  async function save(body: GoalInput) {
    if (editor.item) await api.goals.update(editor.item.id, body)
    else await api.goals.create(body)
    toast.success(editor.item ? 'Meta atualizada.' : 'Meta criada.')
    void refresh()
    editor.setOpen(false)
  }

  return (
    <>
      <PageHeader
        title="Metas"
        description="Objetivos de poupança e quanto falta para chegar lá."
        actions={
          <Button onClick={editor.create}>
            <PlusIcon /> Nova meta
          </Button>
        }
      />
      <p className="flex items-start gap-2 rounded-lg border bg-background p-3 text-sm text-muted-foreground">
        <InfoIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
        Para guardar dinheiro numa meta, lance uma despesa do grupo Poupança (por exemplo, na categoria Investimentos) e
        escolha a meta.
      </p>
      {goals.isError ? (
        <QueryError error={goals.error} onRetry={() => void goals.refetch()} />
      ) : goals.isPending ? (
        <LoadingBlock rows={3} />
      ) : goals.data.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>Nenhuma meta ainda</EmptyTitle>
            <EmptyDescription>Uma reserva de emergência é um bom começo.</EmptyDescription>
          </EmptyHeader>
          <Button onClick={editor.create}>
            <PlusIcon /> Nova meta
          </Button>
        </Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {goals.data.map((goal) => (
            <Card key={goal.id} className={goal.archived ? 'opacity-70' : undefined}>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <CardTitle>{`${goal.icon} ${goal.name}`.trim()}</CardTitle>
                {goal.archived && <Badge variant="secondary">Arquivada</Badge>}
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <ProgressBar
                  label="Progresso"
                  value={goal.saved_cents}
                  max={goal.target_cents}
                  tone="savings"
                  overflowIsBad={false}
                  detail={`${formatCents(goal.saved_cents)} de ${formatCents(goal.target_cents)}`}
                />
                {goal.remaining_cents > 0 && <p className="text-sm">Faltam {formatCents(goal.remaining_cents)}.</p>}
                {pace(goal) && <p className="text-sm text-muted-foreground">{pace(goal)}</p>}
              </CardContent>
              <CardFooter className="flex flex-wrap gap-2">
                <Button variant="ghost" size="sm" onClick={() => editor.edit(goal)}>
                  <PencilIcon /> Editar
                </Button>
                <Button variant="ghost" size="sm" disabled={archive.isPending} onClick={() => archive.mutate(goal)}>
                  {goal.archived ? <ArchiveRestoreIcon /> : <ArchiveIcon />}{' '}
                  {goal.archived ? 'Desarquivar' : 'Arquivar'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => removal.ask(goal)}>
                  <Trash2Icon /> Excluir
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <FormDialog open={editor.open} onOpenChange={editor.setOpen} title={editor.item ? 'Editar meta' : 'Nova meta'}>
        <GoalForm
          key={editor.item?.id ?? 'nova'}
          initial={editor.item}
          onSubmit={save}
          onCancel={() => editor.setOpen(false)}
        />
      </FormDialog>

      <ConfirmDialog
        open={removal.target !== null}
        onOpenChange={(open) => !open && removal.dismiss()}
        title={`Excluir a meta “${removal.target?.name ?? ''}”?`}
        description="Os aportes continuam como lançamentos de poupança, só deixam de estar ligados a esta meta."
        pending={removal.pending}
        actions={[{ label: 'Excluir', destructive: true, onConfirm: removal.confirm }]}
      />
    </>
  )
}
