import { CheckCircle2Icon } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { PageHeader } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Button } from '@/components/ui/button'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { api } from '@/lib/api'
import { useCards, useCategories, useInvoiceImport, useRefreshData } from '@/lib/queries'
import type { InvoiceImportDetail } from '@/lib/types'

import { IdentifiedSection } from './IdentifiedSection'
import { importDescription, importName, isStatement } from './import-labels'
import { ImportActions } from './ImportActions'
import { SkippedSection } from './SkippedSection'
import { StandbySection } from './StandbySection'

function DeleteDialog({
  invoice,
  open,
  onOpenChange,
}: {
  invoice: InvoiceImportDetail
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const refresh = useRefreshData()
  const [pending, setPending] = useState(false)
  const confirmed = Boolean(invoice.confirmed_at)
  const noun = isStatement(invoice) ? 'deste extrato' : 'desta fatura'

  async function remove() {
    setPending(true)
    try {
      await api.invoices.remove(invoice.id)
      toast.success(confirmed ? 'Importação desfeita.' : 'Leitura descartada.')
      void refresh()
      void navigate('/faturas')
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : 'Não foi possível concluir.')
      setPending(false)
    }
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      pending={pending}
      title={confirmed ? 'Desfazer importação?' : 'Descartar leitura?'}
      description={
        confirmed
          ? isStatement(invoice)
            ? 'Os lançamentos criados por este extrato serão apagados.'
            : 'Os lançamentos criados por esta fatura, inclusive parcelas futuras, serão apagados.'
          : `Nada ${noun} foi lançado ainda. Você pode importar o arquivo de novo depois.`
      }
      actions={[{ label: confirmed ? 'Desfazer' : 'Descartar', destructive: true, onConfirm: () => remove() }]}
    />
  )
}

export function InvoiceImportPage() {
  const id = Number(useParams().id)
  const invoice = useInvoiceImport(id)
  const categories = useCategories()
  const cards = useCards()
  const refresh = useRefreshData()
  const [deleting, setDeleting] = useState(false)
  const confirming = useSingleFlight()

  function confirm() {
    void confirming.run(async () => {
      try {
        await api.invoices.confirm(id)
        toast.success('Lançamentos criados.')
        void refresh()
      } catch (failure) {
        toast.error(failure instanceof Error ? failure.message : 'Não foi possível confirmar.')
      }
    })
  }

  if (invoice.isError || categories.isError) {
    return <QueryError error={invoice.error ?? categories.error} onRetry={() => void refresh()} />
  }
  if (invoice.isPending || categories.isPending) return <LoadingBlock rows={4} />

  const data = invoice.data
  const cardName = cards.data?.find((card) => card.id === data.card_id)?.name
  const statement = isStatement(data)
  const onChanged = () => void refresh()
  return (
    <>
      <PageHeader
        title={importName(data, cardName)}
        description={importDescription(data)}
        actions={
          <ImportActions
            invoice={data}
            busy={confirming.pending}
            onConfirm={confirm}
            onDelete={() => setDeleting(true)}
          />
        }
      />
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <CheckCircle2Icon className="size-4 text-emerald-600" aria-hidden />
        {statement
          ? 'Soma confere com os totais impressos no extrato.'
          : 'Soma confere com o total impresso na fatura.'}
        {data.confirmed_at && (statement ? ' Extrato confirmado.' : ' Fatura confirmada.')}
      </p>
      <IdentifiedSection lines={data.lines} categories={categories.data} onChanged={onChanged} />
      <StandbySection lines={data.lines} categories={categories.data} onChanged={onChanged} />
      <SkippedSection lines={data.lines} cards={cards.data ?? []} investment={data.investment} onChanged={onChanged} />
      <Button asChild variant="link" className="self-start px-0">
        <Link to="/faturas">Voltar para as importações</Link>
      </Button>
      <DeleteDialog invoice={data} open={deleting} onOpenChange={setDeleting} />
    </>
  )
}
