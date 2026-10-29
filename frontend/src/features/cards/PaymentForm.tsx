import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'

import { FieldRow, FormError, SubmitButton } from '@/components/form'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { ApiError, api } from '@/lib/api'
import { todayIso } from '@/lib/dates'
import { centsToInput, parseMoneyToCents } from '@/lib/money'
import { useRefreshData } from '@/lib/queries'

interface Errors {
  paid_on?: string
  amount_cents?: string
  form?: string
}

/** Marca a fatura como paga: data (hoje) e valor (o que falta); um valor menor registra pagamento em parte. */
export function PaymentForm({
  cardId,
  month,
  remainingCents,
  onDone,
}: {
  cardId: number
  month: string
  remainingCents: number
  onDone: () => void
}) {
  const refresh = useRefreshData()
  const saving = useSingleFlight()
  const [paidOn, setPaidOn] = useState(todayIso())
  const [amount, setAmount] = useState(centsToInput(remainingCents))
  const [errors, setErrors] = useState<Errors>({})

  function submit(event: FormEvent) {
    event.preventDefault()
    const cents = parseMoneyToCents(amount)
    if (!cents) {
      setErrors({ amount_cents: 'Informe o valor pago.' })
      return
    }
    void saving.run(async () => {
      try {
        await api.cards.pay(cardId, { invoice_month: month, paid_on: paidOn, amount_cents: cents })
        toast.success('Pagamento registrado.')
        void refresh()
        onDone()
      } catch (error) {
        const fields = error instanceof ApiError ? error.fieldErrors : {}
        setErrors({
          paid_on: fields.paid_on,
          amount_cents: fields.amount_cents,
          form: fields.invoice_month ?? (fields.paid_on || fields.amount_cents ? undefined : (error as Error).message),
        })
      }
    })
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border p-3" noValidate>
      <FormError message={errors.form} />
      <div className="grid gap-3 sm:grid-cols-2">
        <FieldRow id="payment-date" label="Data do pagamento" error={errors.paid_on}>
          <Input id="payment-date" type="date" value={paidOn} onChange={(event) => setPaidOn(event.target.value)} />
        </FieldRow>
        <FieldRow id="payment-amount" label="Valor pago" error={errors.amount_cents}>
          <Input
            id="payment-amount"
            inputMode="decimal"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </FieldRow>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancelar
        </Button>
        <SubmitButton submitting={saving.pending} pendingText="Salvando…">
          Salvar pagamento
        </SubmitButton>
      </div>
    </form>
  )
}
