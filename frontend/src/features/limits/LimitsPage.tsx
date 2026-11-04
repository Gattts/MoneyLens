import { PencilIcon, PlusIcon, Trash2Icon } from 'lucide-react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormDialog } from '@/components/FormDialog'
import { MonthPicker, PageHeader } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { useEditor, useRemove } from '@/hooks/useCrud'
import { api } from '@/lib/api'
import { useMonthParam } from '@/hooks/usePeriodParams'
import { useCategories, useLimits, useRefreshData } from '@/lib/queries'
import type { LimitInput, SpendingLimit } from '@/lib/types'

import { LimitBar } from './LimitBar'
import { LimitForm } from './LimitForm'

export function LimitsPage() {
  const [month, setMonth] = useMonthParam()
  const limits = useLimits(month)
  const categories = useCategories()
  const refresh = useRefreshData()
  const editor = useEditor<SpendingLimit>()
  const removal = useRemove<SpendingLimit>(api.limits.remove, 'Teto excluído.')
  const taken = new Set(limits.data?.map((limit) => limit.category_id))
  const available = (categories.data ?? []).filter(
    (category) => category.kind === 'expense' && !category.archived && !taken.has(category.id),
  )

  async function save(body: LimitInput) {
    if (editor.item) {
      const { category_id: _category, ...value } = body // a categoria não muda na edição
      await api.limits.update(editor.item.id, value)
    } else await api.limits.create(body)
    toast.success(editor.item ? 'Teto atualizado.' : 'Teto criado.')
    void refresh()
    editor.setOpen(false)
  }

  const newLimit = (
    <Button onClick={editor.create}>
      <PlusIcon /> Novo teto
    </Button>
  )

  return (
    <>
      <PageHeader
        title="Tetos"
        description="Quanto você quer gastar no máximo em cada categoria, por mês; compras no cartão contam no mês em que a fatura vence. Eu aviso em 50%, 90% e 100%."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <MonthPicker month={month} onChange={setMonth} />
            {newLimit}
          </div>
        }
      />
      {limits.isError ? (
        <QueryError error={limits.error} onRetry={() => void limits.refetch()} />
      ) : limits.isPending ? (
        <LoadingBlock rows={3} />
      ) : limits.data.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>Nenhum teto ainda</EmptyTitle>
            <EmptyDescription>Comece pela categoria em que o dinheiro mais escapa, como comida fora.</EmptyDescription>
          </EmptyHeader>
          {newLimit}
        </Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {limits.data.map((limit) => (
            <Card key={limit.id} data-limit className={limit.active ? undefined : 'opacity-70'}>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-1.5">
                  {limit.icon && <span aria-hidden>{limit.icon}</span>}
                  <span>{limit.name}</span>
                </CardTitle>
                <div className="flex gap-1">
                  {limit.will_exceed && <Badge variant="destructive">Vai estourar</Badge>}
                  {limit.no_income && <Badge variant="secondary">Sem renda neste mês</Badge>}
                  {!limit.active && !limit.no_income && <Badge variant="secondary">Inativo</Badge>}
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {limit.income_percent !== null && (
                  <p className="text-sm text-muted-foreground">{limit.income_percent}% da renda prevista</p>
                )}
                <LimitBar limit={limit} />
              </CardContent>
              <CardFooter className="flex flex-wrap gap-2">
                <Button variant="ghost" size="sm" onClick={() => editor.edit(limit)}>
                  <PencilIcon /> Editar
                </Button>
                <Button variant="ghost" size="sm" onClick={() => removal.ask(limit)}>
                  <Trash2Icon /> Excluir
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <FormDialog open={editor.open} onOpenChange={editor.setOpen} title={editor.item ? 'Editar teto' : 'Novo teto'}>
        <LimitForm
          key={editor.item?.id ?? 'novo'}
          initial={editor.item}
          categories={available}
          onSubmit={save}
          onCancel={() => editor.setOpen(false)}
        />
      </FormDialog>

      <ConfirmDialog
        open={removal.target !== null}
        onOpenChange={(open) => !open && removal.dismiss()}
        title={`Excluir o teto de “${removal.target?.name ?? ''}”?`}
        description="Os alertas deste teto também são apagados."
        pending={removal.pending}
        actions={[{ label: 'Excluir', destructive: true, onConfirm: removal.confirm }]}
      />
    </>
  )
}
