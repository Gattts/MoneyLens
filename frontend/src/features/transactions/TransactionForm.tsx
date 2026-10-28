import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { SegmentedControl } from '@/components/SegmentedControl'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { ClassificationFields } from '@/features/entries/EntryFields'
import { KIND_OPTIONS, defaultBucketOf, kindChange, selectable } from '@/features/entries/entry-rules'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { parseMoneyToCents } from '@/lib/money'
import type { Card, Category, Goal, Kind, Transaction, TransactionCreate } from '@/lib/types'
import { MAX_DATE, MIN_DATE } from '@/lib/validation'

import {
  API_FIELD_MAP,
  FORM_FIELDS,
  MAX_INSTALLMENTS,
  type TransactionFormValues,
  initialValues,
  installmentPreview,
  toPayload,
  transactionSchema,
} from './schema'

export interface TransactionFormProps {
  categories: Category[]
  cards: Card[]
  goals: Goal[]
  initial?: Transaction
  defaultDate?: string
  onSubmit: (payload: TransactionCreate) => Promise<unknown>
  onCancel: () => void
}

export function TransactionForm({
  categories,
  cards,
  goals,
  initial,
  defaultDate,
  onSubmit,
  onCancel,
}: TransactionFormProps) {
  const creating = !initial
  const { register, setValue, handleSubmit, setError, control, formState } = useForm<TransactionFormValues>({
    resolver: zodResolver(transactionSchema),
    defaultValues: initialValues(initial, defaultDate),
  })
  const { errors, isSubmitting } = formState
  const [kind, bucket, paymentMethod, amount, installments] = useWatch({
    control,
    name: ['kind', 'bucket', 'payment_method', 'amount', 'installments'],
  })

  const isExpense = kind === 'expense'
  const onCard = paymentMethod === 'credit_card'
  const totalCents = parseMoneyToCents(amount)
  const count = Number(installments)
  const showPreview = creating && onCard && totalCents && count > 1 && count <= MAX_INSTALLMENTS

  function changeKind(next: Kind) {
    const updates = kindChange(next, paymentMethod)
    setValue('kind', next)
    setValue('category_id', updates.category_id)
    setValue('bucket', updates.bucket)
    setValue('payment_method', updates.payment_method)
  }

  async function submit(values: TransactionFormValues) {
    try {
      await onSubmit(toPayload(values, creating))
    } catch (error) {
      showServerErrors(error, setError, API_FIELD_MAP, FORM_FIELDS)
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
      <FormError message={errors.root?.server?.message} />
      <FieldGroup className="gap-4">
        <SegmentedControl label="Tipo" name="kind" value={kind} options={KIND_OPTIONS} onChange={changeKind} />

        <FieldRow id="description" label="Descrição" error={errors.description?.message}>
          <Input
            {...fieldA11y('description', errors.description?.message)}
            {...register('description')}
            maxLength={120}
            autoComplete="off"
            placeholder={isExpense ? 'Ex.: Mercado do mês' : 'Ex.: Salário'}
          />
        </FieldRow>

        <div className="grid gap-4 sm:grid-cols-2">
          <FieldRow id="amount" label="Valor" error={errors.amount?.message}>
            <Input
              {...fieldA11y('amount', errors.amount?.message)}
              {...register('amount')}
              inputMode="decimal"
              autoComplete="off"
              placeholder="0,00"
            />
          </FieldRow>
          <FieldRow id="date" label="Data" error={errors.date?.message}>
            <Input
              {...fieldA11y('date', errors.date?.message)}
              {...register('date')}
              type="date"
              min={MIN_DATE}
              max={MAX_DATE}
            />
          </FieldRow>
        </div>

        <ClassificationFields
          kind={kind}
          bucket={bucket}
          paymentMethod={paymentMethod}
          categories={categories}
          cards={cards}
          currentCategoryId={initial?.category_id}
          currentCardId={initial?.card_id}
          fields={{
            category: register('category_id', {
              onChange: (event) => setValue('bucket', defaultBucketOf(categories, event.target.value)),
            }),
            bucket: register('bucket'),
            payment: register('payment_method'),
            card: register('card_id'),
          }}
          errors={{
            category: errors.category_id?.message,
            bucket: errors.bucket?.message,
            payment: errors.payment_method?.message,
            card: errors.card_id?.message,
          }}
          besideCard={
            creating && (
              <FieldRow
                id="installments"
                label="Parcelas"
                error={errors.installments?.message}
                description={showPreview ? installmentPreview(totalCents, count) : 'Informe o valor total da compra.'}
              >
                <Input
                  {...fieldA11y('installments', errors.installments?.message)}
                  {...register('installments')}
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={MAX_INSTALLMENTS}
                />
              </FieldRow>
            )
          }
        />

        {isExpense && bucket === 'savings' && (
          <FieldRow
            id="goal_id"
            label="Meta"
            error={errors.goal_id?.message}
            description="Opcional: o valor entra no progresso da meta."
          >
            <NativeSelect
              className="w-full"
              {...fieldA11y('goal_id', errors.goal_id?.message)}
              {...register('goal_id')}
            >
              <NativeSelectOption value="">Nenhuma</NativeSelectOption>
              {selectable(goals, initial?.goal_id).map((goal) => (
                <NativeSelectOption key={goal.id} value={String(goal.id)}>
                  {`${goal.icon} ${goal.name}`.trim()}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FieldRow>
        )}

        <FieldRow id="notes" label="Observações" error={errors.notes?.message}>
          <Textarea {...fieldA11y('notes', errors.notes?.message)} {...register('notes')} maxLength={500} rows={2} />
        </FieldRow>
      </FieldGroup>

      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
