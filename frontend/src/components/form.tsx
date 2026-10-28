import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Field, FieldDescription, FieldError, FieldLabel } from '@/components/ui/field'
import { Spinner } from '@/components/ui/spinner'

interface FieldRowProps {
  id: string
  label: string
  error?: string
  description?: ReactNode
  children: ReactNode
}

/** Rótulo + controle + dica + erro, com o erro ligado ao campo para leitores de tela. */
export function FieldRow({ id, label, error, description, children }: FieldRowProps) {
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children}
      {description && <FieldDescription>{description}</FieldDescription>}
      <FieldError id={`${id}-error`}>{error}</FieldError>
    </Field>
  )
}

export function FormError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
    >
      {message}
    </div>
  )
}

interface SubmitButtonProps {
  submitting: boolean
  children?: ReactNode
  pendingText?: string
  className?: string
}

export function SubmitButton({
  submitting,
  children = 'Salvar',
  pendingText = 'Salvando…',
  className,
}: SubmitButtonProps) {
  return (
    <Button type="submit" disabled={submitting} className={className}>
      {submitting ? (
        <>
          <Spinner /> {pendingText}
        </>
      ) : (
        children
      )}
    </Button>
  )
}

/** Rodapé padrão dos formulários: Cancelar fecha sem salvar; Salvar trava enquanto envia. */
export function FormActions({ submitting, onCancel }: { submitting: boolean; onCancel: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <Button type="button" variant="outline" onClick={onCancel}>
        Cancelar
      </Button>
      <SubmitButton submitting={submitting} />
    </div>
  )
}
