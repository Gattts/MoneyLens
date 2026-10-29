import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { FieldRow, FormError, SubmitButton } from '@/components/form'
import { SegmentedControl } from '@/components/SegmentedControl'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { ApiError, api } from '@/lib/api'
import type { Card, ImportSource } from '@/lib/types'

import { PasswordDialog } from './PasswordDialog'

const SOURCE_OPTIONS = [
  { value: 'card_invoice', label: 'Fatura do cartão' },
  { value: 'account_statement', label: 'Extrato da conta' },
] as const

interface Errors {
  card_id?: string
  file?: string
  form?: string
}

export function ImportForm({ cards }: { cards: Card[] }) {
  const navigate = useNavigate()
  const active = cards.filter((card) => !card.archived)
  const [source, setSource] = useState<ImportSource>('card_invoice')
  const statement = source === 'account_statement'
  const noun = statement ? 'extrato' : 'fatura'
  const [cardId, setCardId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<Errors>({})
  // Mensagem do pop-up de senha; null = fechado.
  const [passwordPrompt, setPasswordPrompt] = useState<string | null>(null)
  const sending = useSingleFlight()
  const submitting = sending.pending
  const cardName = active.find((card) => String(card.id) === cardId)?.name ?? ''

  async function upload(chosen: File, password?: string, save = false) {
    const form = new FormData()
    form.set('source', source)
    if (!statement) form.set('card_id', cardId)
    form.set('file', chosen)
    if (password !== undefined) {
      form.set('password', password)
      form.set('save_password', String(save))
    }
    try {
      const result = await api.invoices.upload(form)
      setPasswordPrompt(null)
      if (result.already_imported) {
        toast.info(statement ? 'Este extrato já tinha sido importado.' : 'Esta fatura já tinha sido importada.')
      }
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
          : { form: error instanceof Error ? error.message : 'Não foi possível ler o arquivo.' },
      )
    }
  }

  function send(password?: string, save = false) {
    if (file) void sending.run(() => upload(file, password, save))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    const missing: Errors = {
      card_id: statement || cardId ? undefined : 'Escolha o cartão.',
      file: file ? undefined : `Escolha o arquivo PDF ${statement ? 'do extrato' : 'da fatura'}.`,
    }
    setErrors(missing)
    if (!missing.card_id && !missing.file) send()
  }

  return (
    <>
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <FormError message={errors.form} />
        <div className="sm:max-w-sm">
          <SegmentedControl
            label="Tipo de arquivo"
            name="import-source"
            value={source}
            options={SOURCE_OPTIONS}
            onChange={(next) => {
              setSource(next)
              setErrors({})
            }}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {!statement && (
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
          )}
          <FieldRow
            id="invoice-file"
            label={`Arquivo ${statement ? 'do extrato' : 'da fatura'} (PDF)`}
            error={errors.file}
          >
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
          Ler {noun}
        </SubmitButton>
      </form>
      {/* Fora do <form>: no React o envio do diálogo (num portal) subiria até o formulário de fora. */}
      <PasswordDialog
        open={passwordPrompt !== null}
        cardName={statement ? null : cardName}
        message={passwordPrompt ?? undefined}
        submitting={submitting}
        onSubmit={(password, save) => send(password, save)}
        onCancel={() => setPasswordPrompt(null)}
      />
    </>
  )
}
