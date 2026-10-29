import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { api } from '@/lib/api'
import { addMonths, formatMonthLabel, monthOf } from '@/lib/dates'
import type { Card, InvoiceLine } from '@/lib/types'

/** Linha do extrato que parece pagamento de fatura: registrar (na sugerida ou na escolhida) ou devolver. */
export function CardPaymentActions({
  line,
  cards,
  onChanged,
}: {
  line: InvoiceLine
  cards: Card[]
  onChanged: () => void
}) {
  const suggestion = line.payment_suggestion
  const months = [addMonths(monthOf(line.date), -1), monthOf(line.date)]
  const [cardId, setCardId] = useState('')
  const [month, setMonth] = useState(months[0])
  const acting = useSingleFlight()

  function act(request: () => Promise<unknown>) {
    void acting.run(async () => {
      try {
        await request()
        onChanged()
      } catch (failure) {
        toast.error(failure instanceof Error ? failure.message : 'Não foi possível concluir.')
      }
    })
  }

  function register() {
    const body = suggestion
      ? { card_id: suggestion.card_id, invoice_month: suggestion.invoice_month }
      : { card_id: Number(cardId), invoice_month: month }
    act(() => api.invoiceLines.registerPayment(line.id, body))
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      {!suggestion && (
        <>
          <NativeSelect
            aria-label="Cartão do pagamento"
            value={cardId}
            onChange={(event) => setCardId(event.target.value)}
          >
            <NativeSelectOption value="">Cartão…</NativeSelectOption>
            {cards
              .filter((card) => !card.archived)
              .map((card) => (
                <NativeSelectOption key={card.id} value={String(card.id)}>
                  {card.name}
                </NativeSelectOption>
              ))}
          </NativeSelect>
          <NativeSelect aria-label="Fatura paga" value={month} onChange={(event) => setMonth(event.target.value)}>
            {months.map((option) => (
              <NativeSelectOption key={option} value={option}>
                Fatura de {formatMonthLabel(option)}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </>
      )}
      <Button size="sm" disabled={acting.pending || (!suggestion && !cardId)} onClick={register}>
        Registrar pagamento
      </Button>
      <Button
        size="sm"
        variant="outline"
        disabled={acting.pending}
        onClick={() => act(() => api.invoiceLines.include(line.id))}
      >
        Não é pagamento
      </Button>
    </span>
  )
}
