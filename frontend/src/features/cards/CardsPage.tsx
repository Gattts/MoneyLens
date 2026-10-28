import { ArchiveIcon, ArchiveRestoreIcon, InfoIcon, PencilIcon, PlusIcon, ReceiptIcon, Trash2Icon } from 'lucide-react'
import { useState } from 'react'
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
import { formatDate } from '@/lib/dates'
import { INVOICE_STATUS_LABELS } from '@/lib/labels'
import { formatCents } from '@/lib/money'
import { useCards, useRefreshData } from '@/lib/queries'
import type { Card as CreditCard, CardInput } from '@/lib/types'

import { CardForm } from './CardForm'
import { InvoiceDialog } from './InvoiceDialog'

function toInput(card: CreditCard): CardInput {
  return {
    name: card.name,
    limit_cents: card.limit_cents,
    closing_day: card.closing_day,
    due_day: card.due_day,
    archived: card.archived,
  }
}

export function CardsPage() {
  const cards = useCards()
  const refresh = useRefreshData()
  const editor = useEditor<CreditCard>()
  const removal = useRemove<CreditCard>(api.cards.remove, 'Cartão excluído.')
  const archive = useQuickAction(
    (card: CreditCard) => api.cards.update(card.id, { ...toInput(card), archived: !card.archived }),
    (card) => (card.archived ? `“${card.name}” voltou para a lista.` : `“${card.name}” arquivado.`),
  )
  const [invoiceCard, setInvoiceCard] = useState<CreditCard | null>(null)

  async function save(body: CardInput) {
    if (editor.item) await api.cards.update(editor.item.id, body)
    else await api.cards.create(body)
    toast.success(editor.item ? 'Cartão atualizado.' : 'Cartão cadastrado.')
    void refresh()
    editor.setOpen(false)
  }

  return (
    <>
      <PageHeader
        title="Cartões"
        description="Faturas calculadas pelo dia de fechamento de cada cartão."
        actions={
          <Button onClick={editor.create}>
            <PlusIcon /> Novo cartão
          </Button>
        }
      />
      <p className="flex items-start gap-2 rounded-lg border bg-background p-3 text-sm text-muted-foreground">
        <InfoIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
        Não lance o pagamento da fatura como despesa: cada compra no cartão já conta como gasto no mês em que foi feita.
      </p>
      {cards.isError ? (
        <QueryError error={cards.error} onRetry={() => void cards.refetch()} />
      ) : cards.isPending ? (
        <LoadingBlock rows={3} />
      ) : cards.data.length === 0 ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>Nenhum cartão cadastrado</EmptyTitle>
            <EmptyDescription>
              Cadastre o limite e os dias de fechamento e vencimento para acompanhar as faturas.
            </EmptyDescription>
          </EmptyHeader>
          <Button onClick={editor.create}>
            <PlusIcon /> Novo cartão
          </Button>
        </Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {cards.data.map((card) => (
            <Card key={card.id} className={card.archived ? 'opacity-70' : undefined}>
              <CardHeader className="flex flex-row items-center justify-between gap-2">
                <CardTitle>{card.name}</CardTitle>
                {card.archived && <Badge variant="secondary">Arquivado</Badge>}
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <ProgressBar
                  label="Limite usado"
                  value={card.used_cents}
                  max={card.limit_cents}
                  tone="neutral"
                  detail={`${formatCents(card.used_cents)} de ${formatCents(card.limit_cents)} · disponível ${formatCents(card.available_cents)}`}
                />
                <div className="rounded-lg bg-muted/60 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span>Fatura atual</span>
                    <Badge variant="outline">{INVOICE_STATUS_LABELS[card.current_invoice.status]}</Badge>
                  </div>
                  <p className="mt-1 text-xl font-semibold tabular-nums">
                    {formatCents(card.current_invoice.total_cents)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Fecha em {formatDate(card.current_invoice.closing_date)} · vence em{' '}
                    {formatDate(card.current_invoice.due_date)}
                  </p>
                </div>
              </CardContent>
              <CardFooter className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => setInvoiceCard(card)}>
                  <ReceiptIcon /> Ver faturas
                </Button>
                <Button variant="ghost" size="sm" onClick={() => editor.edit(card)}>
                  <PencilIcon /> Editar
                </Button>
                <Button variant="ghost" size="sm" disabled={archive.isPending} onClick={() => archive.mutate(card)}>
                  {card.archived ? <ArchiveRestoreIcon /> : <ArchiveIcon />}{' '}
                  {card.archived ? 'Desarquivar' : 'Arquivar'}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => removal.ask(card)}>
                  <Trash2Icon /> Excluir
                </Button>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}

      <FormDialog
        open={editor.open}
        onOpenChange={editor.setOpen}
        title={editor.item ? 'Editar cartão' : 'Novo cartão'}
      >
        <CardForm
          key={editor.item?.id ?? 'novo'}
          initial={editor.item}
          onSubmit={save}
          onCancel={() => editor.setOpen(false)}
        />
      </FormDialog>

      {invoiceCard && <InvoiceDialog card={invoiceCard} onClose={() => setInvoiceCard(null)} />}

      <ConfirmDialog
        open={removal.target !== null}
        onOpenChange={(open) => !open && removal.dismiss()}
        title={`Excluir o cartão “${removal.target?.name ?? ''}”?`}
        description="Só é possível excluir um cartão sem compras. Se ele tiver histórico, arquive-o para escondê-lo."
        pending={removal.pending}
        actions={[{ label: 'Excluir', destructive: true, onConfirm: removal.confirm }]}
      />
    </>
  )
}
