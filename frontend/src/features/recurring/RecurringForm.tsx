import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { SegmentedControl } from '@/components/SegmentedControl'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ClassificationFields } from '@/features/entries/EntryFields'
import {
  KIND_OPTIONS,
  checkEntryChoice,
  defaultBucketOf,
  entryFields,
  kindChange,
} from '@/features/entries/entry-rules'
import { formatMonthInput, parseMonthInput } from '@/lib/dates'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { centsToInput, parseMoneyToCents } from '@/lib/money'
import type { Card, Category, Kind, RecurringInput, RecurringRule } from '@/lib/types'
import { integerText } from '@/lib/validation'

const INVALID_MONTH = 'Mês inválido. Use MM/AAAA, por exemplo 07/2027.'

const schema = z
  .object({
    ...entryFields,
    day_of_month: integerText(1, 31, 'Use um dia de 1 a 31.'),
    start_month: z.string().superRefine((value, ctx) => {
      if (!value.trim()) ctx.addIssue({ code: 'custom', message: 'Informe o mês de início.' })
      else if (!parseMonthInput(value)) ctx.addIssue({ code: 'custom', message: INVALID_MONTH })
    }),
    // Vazio = sem data para acabar. Qualquer outra coisa precisa ser um mês válido: nunca descartamos em silêncio.
    end_month: z.string().refine((value) => !value.trim() || parseMonthInput(value) !== null, INVALID_MONTH),
  })
  .superRefine((values, ctx) => {
    const start = parseMonthInput(values.start_month)
    const end = parseMonthInput(values.end_month)
    if (start && end && end < start)
      ctx.addIssue({
        code: 'custom',
        path: ['end_month'],
        message: 'O mês final precisa ser igual ou posterior ao inicial.',
      })
    checkEntryChoice(values, ctx)
  })
type Values = z.infer<typeof schema>

interface RecurringFormProps {
  categories: Category[]
  cards: Card[]
  initial?: RecurringRule
  defaultMonth: string
  onSubmit: (body: RecurringInput) => Promise<unknown>
  onCancel: () => void
}

function defaults(initial: RecurringRule | undefined, defaultMonth: string): Values {
  if (!initial) {
    return {
      kind: 'expense',
      description: '',
      amount: '',
      day_of_month: '',
      category_id: '',
      bucket: '',
      payment_method: 'pix',
      card_id: '',
      start_month: formatMonthInput(defaultMonth),
      end_month: '',
      notes: '',
    }
  }
  return {
    kind: initial.kind,
    description: initial.description,
    amount: centsToInput(initial.amount_cents),
    day_of_month: String(initial.day_of_month),
    category_id: String(initial.category_id),
    bucket: initial.bucket ?? '',
    payment_method: initial.payment_method,
    card_id: initial.card_id ? String(initial.card_id) : '',
    start_month: formatMonthInput(initial.start_month),
    end_month: initial.end_month ? formatMonthInput(initial.end_month) : '',
    notes: initial.notes,
  }
}

export function RecurringForm({ categories, cards, initial, defaultMonth, onSubmit, onCancel }: RecurringFormProps) {
  const { register, handleSubmit, setValue, setError, control, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: defaults(initial, defaultMonth),
  })
  const { errors, isSubmitting } = formState
  const [kind, bucket, paymentMethod] = useWatch({ control, name: ['kind', 'bucket', 'payment_method'] })

  function changeKind(next: Kind) {
    const updates = kindChange(next, paymentMethod)
    setValue('kind', next)
    setValue('category_id', updates.category_id)
    setValue('bucket', updates.bucket)
    setValue('payment_method', updates.payment_method)
  }

  async function submit(values: Values) {
    const onCard = values.payment_method === 'credit_card'
    try {
      await onSubmit({
        description: values.description,
        kind: values.kind,
        amount_cents: parseMoneyToCents(values.amount) ?? 0,
        category_id: Number(values.category_id),
        bucket: values.kind === 'expense' && values.bucket ? values.bucket : null,
        day_of_month: Number(values.day_of_month),
        payment_method: values.payment_method,
        card_id: onCard ? Number(values.card_id) : null,
        start_month: parseMonthInput(values.start_month) ?? '',
        end_month: parseMonthInput(values.end_month),
        notes: values.notes,
      })
    } catch (error) {
      showServerErrors(error, setError, { amount_cents: 'amount' }, Object.keys(schema.shape))
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
            placeholder="Ex.: Aluguel"
          />
        </FieldRow>
        <div className="grid gap-4 sm:grid-cols-2">
          <FieldRow id="amount" label="Valor" error={errors.amount?.message}>
            <Input
              {...fieldA11y('amount', errors.amount?.message)}
              {...register('amount')}
              inputMode="decimal"
              placeholder="0,00"
            />
          </FieldRow>
          <FieldRow
            id="day_of_month"
            label="Dia do mês"
            error={errors.day_of_month?.message}
            description="Em meses mais curtos, vale o último dia."
          >
            <Input
              {...fieldA11y('day_of_month', errors.day_of_month?.message)}
              {...register('day_of_month')}
              type="number"
              inputMode="numeric"
              min={1}
              max={31}
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
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <FieldRow id="start_month" label="Começa em" error={errors.start_month?.message}>
            <Input
              {...fieldA11y('start_month', errors.start_month?.message)}
              {...register('start_month')}
              inputMode="numeric"
              autoComplete="off"
              maxLength={7}
              placeholder="MM/AAAA"
            />
          </FieldRow>
          <FieldRow
            id="end_month"
            label="Termina em (opcional)"
            error={errors.end_month?.message}
            description="Deixe vazio se não tiver data para acabar. Parcelado em 10×? Coloque o 10º mês."
          >
            <Input
              {...fieldA11y('end_month', errors.end_month?.message)}
              {...register('end_month')}
              inputMode="numeric"
              autoComplete="off"
              maxLength={7}
              placeholder="MM/AAAA"
            />
          </FieldRow>
        </div>
        <FieldRow id="notes" label="Observações" error={errors.notes?.message}>
          <Textarea {...fieldA11y('notes', errors.notes?.message)} {...register('notes')} maxLength={500} rows={2} />
        </FieldRow>
      </FieldGroup>
      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
