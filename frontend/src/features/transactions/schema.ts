import { z } from 'zod'

import { todayIso } from '@/lib/dates'
import { centsToInput, formatCents, parseMoneyToCents } from '@/lib/money'
import type { PaymentMethod, Transaction, TransactionCreate } from '@/lib/types'
import { dateField, integerText } from '@/lib/validation'

import { checkEntryChoice, entryFields } from '../entries/entry-rules'

/** Cartão parcela na fatura; Pix e boleto parcelados debitam uma parcela por mês (a API aceita só estes). */
export const allowsInstallments = (method: PaymentMethod) =>
  method === 'credit_card' || method === 'pix' || method === 'bank_slip'

export const MAX_INSTALLMENTS = 48

export const transactionSchema = z
  .object({
    ...entryFields,
    date: dateField(),
    installments: integerText(1, MAX_INSTALLMENTS, `Use de 1 a ${MAX_INSTALLMENTS} parcelas.`),
    goal_id: z.string(),
  })
  .superRefine(checkEntryChoice)

export type TransactionFormValues = z.infer<typeof transactionSchema>

/** Nome do campo da API → nome do campo do formulário (quando diferem). */
export const API_FIELD_MAP = { amount_cents: 'amount' } as const
export const FORM_FIELDS = Object.keys(transactionSchema.shape)

export function initialValues(initial?: Transaction, defaultDate = todayIso()): TransactionFormValues {
  if (!initial) {
    return {
      kind: 'expense',
      description: '',
      amount: '',
      date: defaultDate,
      category_id: '',
      bucket: '',
      payment_method: 'pix',
      card_id: '',
      installments: '1',
      goal_id: '',
      notes: '',
    }
  }
  return {
    kind: initial.kind,
    description: initial.description,
    amount: centsToInput(initial.amount_cents),
    date: initial.date,
    category_id: String(initial.category_id),
    bucket: initial.bucket ?? '',
    payment_method: initial.payment_method,
    card_id: initial.card_id ? String(initial.card_id) : '',
    installments: '1',
    goal_id: initial.goal_id ? String(initial.goal_id) : '',
    notes: initial.notes,
  }
}

export function toPayload(values: TransactionFormValues, creating: boolean): TransactionCreate {
  const onCard = values.payment_method === 'credit_card'
  const isExpense = values.kind === 'expense'
  const payload: TransactionCreate = {
    description: values.description,
    kind: values.kind,
    amount_cents: parseMoneyToCents(values.amount) ?? 0,
    date: values.date,
    category_id: Number(values.category_id),
    bucket: isExpense && values.bucket ? values.bucket : null,
    payment_method: values.payment_method,
    card_id: onCard ? Number(values.card_id) : null,
    goal_id: isExpense && values.bucket === 'savings' && values.goal_id ? Number(values.goal_id) : null,
    notes: values.notes,
  }
  // Parcelas só existem na criação; a API recusa o campo na edição.
  const installments = allowsInstallments(values.payment_method) ? Number(values.installments) : 1
  return creating ? { ...payload, installments } : payload
}

/** "3× de R$ 33,33 (a primeira de R$ 33,34)": mesma divisão que a API faz. */
export function installmentPreview(totalCents: number, count: number): string {
  const base = Math.floor(totalCents / count)
  const remainder = totalCents % count
  const text = `${count}× de ${formatCents(base)}`.replace(/\s/g, ' ')
  if (remainder === 0) return text
  const bigger = formatCents(base + 1).replace(/\s/g, ' ')
  return remainder === 1 ? `${text} (a primeira de ${bigger})` : `${text} (as ${remainder} primeiras de ${bigger})`
}
