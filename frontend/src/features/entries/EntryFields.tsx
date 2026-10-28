/**
 * Campos que lançamentos e fixas têm em comum: categoria, grupo do orçamento, forma de pagamento e cartão.
 * Cada campo recebe o resultado de `register(...)`, sem depender do tipo de formulário que o usa.
 */
import type { ReactNode } from 'react'
import type { UseFormRegisterReturn } from 'react-hook-form'

import { FieldRow } from '@/components/form'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { fieldA11y } from '@/lib/forms'
import { BUCKET_HINTS, BUCKET_LABELS, BUCKETS, PAYMENT_LABELS, PAYMENT_METHODS } from '@/lib/labels'
import type { Bucket, Card, Category, Kind, PaymentMethod } from '@/lib/types'

import { selectable } from './entry-rules'

interface FieldProps {
  registration: UseFormRegisterReturn
  error?: string
}

export function CategoryField({
  registration,
  error,
  categories,
  kind,
  currentId,
}: FieldProps & { categories: Category[]; kind: Kind; currentId?: number }) {
  const options = selectable(categories, currentId).filter((category) => category.kind === kind)
  const kindName = kind === 'income' ? 'receita' : 'despesa'
  const hint =
    options.length === 0 ? `Nenhuma categoria de ${kindName} ativa. Crie uma na página Categorias.` : undefined
  return (
    <FieldRow id={registration.name} label="Categoria" error={error} description={hint}>
      <NativeSelect className="w-full" {...fieldA11y(registration.name, error)} {...registration}>
        <NativeSelectOption value="">Escolha…</NativeSelectOption>
        {options.map((category) => (
          <NativeSelectOption key={category.id} value={String(category.id)}>
            {`${category.icon} ${category.name}`.trim()}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </FieldRow>
  )
}

export function BucketField({ registration, error, bucket }: FieldProps & { bucket: Bucket | '' }) {
  return (
    <FieldRow
      id={registration.name}
      label="Grupo do orçamento"
      error={error}
      description={bucket ? BUCKET_HINTS[bucket] : 'Vem da categoria; mude se este gasto for diferente.'}
    >
      <NativeSelect className="w-full" {...fieldA11y(registration.name, error)} {...registration}>
        <NativeSelectOption value="">Escolha…</NativeSelectOption>
        {BUCKETS.map((value) => (
          <NativeSelectOption key={value} value={value}>
            {BUCKET_LABELS[value]}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </FieldRow>
  )
}

export function PaymentMethodField({ registration, error, kind }: FieldProps & { kind: Kind }) {
  return (
    <FieldRow id={registration.name} label="Forma de pagamento" error={error}>
      <NativeSelect className="w-full" {...fieldA11y(registration.name, error)} {...registration}>
        {PAYMENT_METHODS.filter((method) => kind === 'expense' || method !== 'credit_card').map((method) => (
          <NativeSelectOption key={method} value={method}>
            {PAYMENT_LABELS[method]}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </FieldRow>
  )
}

export function CardField({
  registration,
  error,
  cards,
  currentId,
}: FieldProps & { cards: Card[]; currentId?: number | null }) {
  const options = selectable(cards, currentId)
  return (
    <FieldRow
      id={registration.name}
      label="Cartão"
      error={error}
      description={options.length === 0 ? 'Nenhum cartão ativo. Cadastre um na página Cartões.' : undefined}
    >
      <NativeSelect className="w-full" {...fieldA11y(registration.name, error)} {...registration}>
        <NativeSelectOption value="">Escolha…</NativeSelectOption>
        {options.map((card) => (
          <NativeSelectOption key={card.id} value={String(card.id)}>
            {card.name}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </FieldRow>
  )
}

interface ClassificationFieldsProps {
  kind: Kind
  bucket: Bucket | ''
  paymentMethod: PaymentMethod
  categories: Category[]
  cards: Card[]
  currentCategoryId?: number
  currentCardId?: number | null
  fields: Record<'category' | 'bucket' | 'payment' | 'card', UseFormRegisterReturn>
  errors: Partial<Record<'category' | 'bucket' | 'payment' | 'card', string>>
  /** Campo extra ao lado do cartão, como o número de parcelas. */
  besideCard?: ReactNode
}

/** Categoria, grupo do orçamento, forma de pagamento e cartão, na ordem e com as regras de sempre. */
export function ClassificationFields({
  kind,
  bucket,
  paymentMethod,
  categories,
  cards,
  currentCategoryId,
  currentCardId,
  fields,
  errors,
  besideCard,
}: ClassificationFieldsProps) {
  return (
    <>
      <CategoryField
        registration={fields.category}
        error={errors.category}
        categories={categories}
        kind={kind}
        currentId={currentCategoryId}
      />
      {kind === 'expense' && <BucketField registration={fields.bucket} error={errors.bucket} bucket={bucket} />}
      <PaymentMethodField registration={fields.payment} error={errors.payment} kind={kind} />
      {paymentMethod === 'credit_card' && (
        <div className="grid gap-4 sm:grid-cols-2">
          <CardField registration={fields.card} error={errors.card} cards={cards} currentId={currentCardId} />
          {besideCard}
        </div>
      )}
    </>
  )
}
