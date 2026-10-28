import { type FormEvent, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { FieldRow, FormError, SubmitButton } from '@/components/form'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { ApiError, api } from '@/lib/api'
import type { Card } from '@/lib/types'

import { PasswordDialog } from './PasswordDialog'

interface Errors {
  card_id?: string
  file?: string
  form?: string
}

export function ImportForm({ cards }: { cards: Card[] }) {
  const navigate = useNavigate()
  const active = cards.filter((card) => !card.archived)
  const [cardId, setCardId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  const [submitting, setSubmitting] = useState(false)
  // Mensagem do pop-up de senha; null = fechado.
  const [passwordPrompt, setPasswordPrompt] = useState<string | null>(null)
  // Trava síncrona: o 2º clique de um clique duplo chega antes de o botão desabilitar.
  const inFlight = useRef(false)
  const cardName = active.find((card) => String(card.id) === cardId)?.name ?? ''

  async function send(password?: string, save = false) {
    if (inFlight.current || !file) return
    inFlight.current = true
    setSubmitting(true)
    const form = new FormData()
    form.set('card_id', cardId)
    form.set('file', file)
    if (password !== undefined) {
      form.set('password', password)
      form.set('save_password', String(save))
    }
    try {
      const result = await api.invoices.upload(form)
      setPasswordPrompt(null)
      if (result.already_imported) toast.info('Esta fatura já tinha sido importada.')
      void navigate(`/faturas/${result.id}`)
    } catch (error) {
      if (error instanceof ApiError && error.fieldErrors.password) {
        setPasswordPrompt(error.fieldErrors.password)
        return
      }
      setPasswordPrompt(null)
      const fieldErrors = error instanceof ApiError ? error.fieldErrors : {}
      setErrors(
        fieldErrors.file || fieldErrors.card_id
          ? { file: fieldErrors.file, card_id: fieldErrors.card_id }
          : { form: error instanceof Error ? error.message : 'Não foi possível ler a fatura.' },
      )
    } finally {
      inFlight.current = false
      setSubmitting(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const missing: Errors = {
      card_id: cardId ? undefined : 'Escolha o cartão.',
      file: file ? undefined : 'Escolha o arquivo PDF da fatura.',
    }
    setErrors(missing)
    if (!missing.card_id && !missing.file) void send()
  }

  return (
    <>
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <FormError message={errors.form} />
        <div className="grid gap-4 sm:grid-cols-2">
          <FieldRow
            id="invoice-card"
            label="Cartão"
            error={errors.card_id}
            description={active.length === 0 ? 'Nenhum cartão ativo. Cadastre um na página Cartões.' : undefined}
          >
            <NativeSelect
              id="invoice-card"
              className="w-full"
              value={cardId}
              aria-invalid={errors.card_id ? true : undefined}
              onChange={(event) => setCardId(event.target.value)}
            >
              <NativeSelectOption value="">Escolha…</NativeSelectOption>
              {active.map((card) => (
                <NativeSelectOption key={card.id} value={String(card.id)}>
                  {card.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FieldRow>
          <FieldRow id="invoice-file" label="Arquivo da fatura (PDF)" error={errors.file}>
            <Input
              id="invoice-file"
              type="file"
              accept="application/pdf"
              aria-invalid={errors.file ? true : undefined}
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </FieldRow>
        </div>
        <SubmitButton submitting={submitting} pendingText="Lendo… pode levar alguns segundos" className="self-start">
          Ler fatura
        </SubmitButton>
      </form>
      {/* Fora do <form>: no React o envio do diálogo (num portal) subiria até o formulário de fora. */}
      <PasswordDialog
        open={passwordPrompt !== null}
        cardName={cardName}
        message={passwordPrompt ?? undefined}
        submitting={submitting}
        onSubmit={(password, save) => void send(password, save)}
        onCancel={() => setPasswordPrompt(null)}
      />
    </>
  )
}
