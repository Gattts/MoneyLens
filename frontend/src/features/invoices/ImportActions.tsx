import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import type { InvoiceImportDetail } from '@/lib/types'

export function ImportActions({
  invoice,
  busy,
  onConfirm,
  onDelete,
}: {
  invoice: InvoiceImportDetail
  busy: boolean
  onConfirm: () => void
  onDelete: () => void
}) {
  const identified = invoice.lines.filter((line) => line.status === 'identified').length
  if (invoice.confirmed_at) {
    return (
      <Button variant="outline" onClick={onDelete}>
        Desfazer importação
      </Button>
    )
  }
  return (
    <>
      {identified > 0 && (
        <Button disabled={busy} onClick={onConfirm}>
          {busy && <Spinner />}
          Confirmar {identified}
        </Button>
      )}
      <Button variant="outline" onClick={onDelete}>
        Descartar leitura
      </Button>
    </>
  )
}
