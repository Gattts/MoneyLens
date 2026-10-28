import { type FormEvent, useState } from 'react'

import { FieldRow, SubmitButton } from '@/components/form'
import { FormDialog } from '@/components/FormDialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface PasswordDialogProps {
  open: boolean
  cardName: string
  /** Mensagem do servidor: "Esta fatura tem senha.", "Senha incorreta."… */
  message?: string
  submitting: boolean
  onSubmit: (password: string, save: boolean) => void
  onCancel: () => void
}

/** Pede a senha do PDF. Salvar no cartão é escolha da pessoa (desmarcado); sem isso a senha é descartada. */
export function PasswordDialog({ open, cardName, message, submitting, onSubmit, onCancel }: PasswordDialogProps) {
  const [password, setPassword] = useState('')
  const [save, setSave] = useState(false)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (password) onSubmit(password, save)
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={(next) => !next && onCancel()}
      title="Fatura protegida por senha"
      description="Esta fatura é protegida por senha. Digite a senha para a leitura."
    >
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <FieldRow id="invoice-password" label="Senha da fatura" error={message}>
          <Input
            id="invoice-password"
            type="password"
            autoComplete="off"
            value={password}
            aria-invalid={message ? true : undefined}
            aria-describedby={message ? 'invoice-password-error' : undefined}
            onChange={(event) => setPassword(event.target.value)}
          />
        </FieldRow>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-0.5 size-4"
            checked={save}
            onChange={(event) => setSave(event.target.checked)}
          />
          Salvar a senha no cartão {cardName} para as próximas faturas
        </label>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancelar
          </Button>
          <SubmitButton submitting={submitting} pendingText="Abrindo…">
            Abrir fatura
          </SubmitButton>
        </div>
      </form>
    </FormDialog>
  )
}
