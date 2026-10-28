import { type ReactNode, useRef, useState } from 'react'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

interface FormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  children: ReactNode
}

/**
 * Janela para formulários. Clique fora não fecha, e Esc ou o "X" perguntam antes de descartar o que foi
 * digitado. Os botões Cancelar e Salvar dos formulários fecham direto (são escolhas explícitas).
 */
export function FormDialog({ open, onOpenChange, title, description, children }: FormDialogProps) {
  const edited = useRef(false)
  const [confirmingDiscard, setConfirmingDiscard] = useState(false)

  function requestClose() {
    if (edited.current) setConfirmingDiscard(true)
    else onOpenChange(false)
  }

  return (
    <>
      <Dialog open={open} onOpenChange={(next) => (next ? onOpenChange(true) : requestClose())}>
        <DialogContent
          className="max-h-[90svh] overflow-y-auto sm:max-w-lg"
          onOpenAutoFocus={() => {
            edited.current = false
          }}
          onInput={() => {
            edited.current = true
          }}
          onInteractOutside={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description ? (
              <DialogDescription>{description}</DialogDescription>
            ) : (
              <DialogDescription className="sr-only">{title}</DialogDescription>
            )}
          </DialogHeader>
          {children}
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={confirmingDiscard}
        onOpenChange={setConfirmingDiscard}
        title="Descartar o que foi digitado?"
        description="As informações deste formulário ainda não foram salvas."
        cancelLabel="Continuar editando"
        actions={[
          {
            label: 'Descartar',
            destructive: true,
            onConfirm: () => {
              setConfirmingDiscard(false)
              onOpenChange(false)
            },
          },
        ]}
      />
    </>
  )
}
