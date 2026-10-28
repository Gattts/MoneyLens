/** Regras compartilhadas pelos formulários de lançamento e de fixa. */
import { z } from 'zod'

import { BUCKETS, KIND_LABELS, PAYMENT_LABELS, PAYMENT_METHODS } from '@/lib/labels'
import type { Bucket, Card, Category, Kind, PaymentMethod } from '@/lib/types'
import { moneyField } from '@/lib/validation'

export const KIND_OPTIONS = [
  { value: 'expense', label: KIND_LABELS.expense },
  { value: 'income', label: KIND_LABELS.income },
] as const

/** Campos que lançamento e fixa têm em comum, com as mesmas mensagens. */
export const entryFields = {
  kind: z.enum(['expense', 'income']),
  description: z.string().trim().min(1, 'Informe a descrição.').max(120, 'Use no máximo 120 caracteres.'),
  amount: moneyField(),
  category_id: z.string().min(1, 'Escolha a categoria.'),
  bucket: z.enum([...BUCKETS, '']),
  payment_method: z.enum(PAYMENT_METHODS),
  card_id: z.string(),
  notes: z.string().trim().max(500, 'Use no máximo 500 caracteres.'),
}

interface EntryChoice {
  kind: Kind
  bucket: Bucket | ''
  payment_method: PaymentMethod
  card_id: string
}

/** Regras entre campos: despesa precisa de grupo; cartão de crédito precisa do cartão. */
export function checkEntryChoice(values: EntryChoice, ctx: z.RefinementCtx) {
  if (values.kind === 'expense' && !values.bucket)
    ctx.addIssue({ code: 'custom', path: ['bucket'], message: 'Escolha o grupo do orçamento.' })
  if (values.payment_method === 'credit_card' && !values.card_id)
    ctx.addIssue({ code: 'custom', path: ['card_id'], message: 'Escolha o cartão.' })
}

/** Itens ativos, mais o já escolhido (editar um registro antigo não pode perder o vínculo). */
export function selectable<T extends { id: number; archived: boolean }>(items: T[], currentId?: number | null) {
  return items.filter((item) => !item.archived || item.id === currentId)
}

/** O que muda no formulário quando a pessoa troca entre despesa e receita. */
export function kindChange(next: Kind, paymentMethod: PaymentMethod) {
  const keepsPayment = next === 'expense' || paymentMethod !== 'credit_card'
  return { category_id: '', bucket: '' as const, payment_method: keepsPayment ? paymentMethod : ('pix' as const) }
}

export function defaultBucketOf(categories: Category[], categoryId: string): Bucket | '' {
  return categories.find((category) => String(category.id) === categoryId)?.default_bucket ?? ''
}

/** Como o pagamento aparece nas listas: o nome do cartão, ou a forma de pagamento. */
export function paymentLabel(method: PaymentMethod, cardId: number | null, cards: Card[]): string {
  if (cardId === null) return PAYMENT_LABELS[method]
  return cards.find((card) => card.id === cardId)?.name ?? PAYMENT_LABELS.credit_card
}
