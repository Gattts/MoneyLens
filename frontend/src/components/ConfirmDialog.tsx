import type { ReactNode } from 'react'

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
  onConfirm: () => void
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
  return (
    <AlertDialog open={open} onOpenChange={(next) => !pending && onOpenChange(next)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>{cancelLabel}</AlertDialogCancel>
          {actions.map((action) => (
            <Button
              key={action.label}
              variant={action.destructive ? 'destructive' : 'default'}
              disabled={pending}
              onClick={action.onConfirm}
            >
              {pending && <Spinner />}
              {action.label}
            </Button>
          ))}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
