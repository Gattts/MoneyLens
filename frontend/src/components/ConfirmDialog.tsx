import type { ReactNode } from 'react'

import { useSingleFlight } from '@/hooks/useSingleFlight'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

export interface ConfirmAction {
  label: string
  /** Devolva a Promise da ação: a janela fica travada até ela terminar (clique duplo não repete). */
  onConfirm: () => void | Promise<unknown>
  destructive?: boolean
}

interface ConfirmDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: ReactNode
  actions: ConfirmAction[]
  pending?: boolean
  cancelLabel?: string
}

/** Confirmação antes de ações irreversíveis. Os botões ficam travados enquanto a ação roda. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  actions,
  pending = false,
  cancelLabel = 'Cancelar',
}: ConfirmDialogProps) {
  const flight = useSingleFlight()
  const busy = pending || flight.pending
  return (
    <AlertDialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy}>{cancelLabel}</AlertDialogCancel>
          {actions.map((action) => (
            <Button
              key={action.label}
              variant={action.destructive ? 'destructive' : 'default'}
              disabled={busy}
              onClick={() => void flight.run(async () => action.onConfirm())}
            >
              {busy && <Spinner />}
              {action.label}
            </Button>
          ))}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
