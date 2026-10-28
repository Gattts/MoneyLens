import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { centsToInput, parseMoneyToCents } from '@/lib/money'
import type { Card, CardInput } from '@/lib/types'
import { integerText, moneyField } from '@/lib/validation'

const day = integerText(1, 31, 'Use um dia de 1 a 31.')
const schema = z.object({
  name: z.string().trim().min(1, 'Informe o nome do cartão.').max(60, 'Use no máximo 60 caracteres.'),
  limit: moneyField({ emptyMessage: 'Informe o limite (pode ser 0).', allowZero: true }),
  closing_day: day,
  due_day: day,
})
type Values = z.infer<typeof schema>

interface CardFormProps {
  initial?: Card
  onSubmit: (body: CardInput) => Promise<unknown>
  onCancel: () => void
}

export function CardForm({ initial, onSubmit, onCancel }: CardFormProps) {
  const { register, handleSubmit, setError, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: initial
      ? {
          name: initial.name,
          limit: centsToInput(initial.limit_cents),
          closing_day: String(initial.closing_day),
          due_day: String(initial.due_day),
        }
      : { name: '', limit: '', closing_day: '', due_day: '' },
  })
  const { errors, isSubmitting } = formState

  async function submit(values: Values) {
    try {
      await onSubmit({
        name: values.name,
        limit_cents: parseMoneyToCents(values.limit) ?? 0,
        closing_day: Number(values.closing_day),
        due_day: Number(values.due_day),
        archived: initial?.archived ?? false,
      })
    } catch (error) {
      showServerErrors(error, setError, { limit_cents: 'limit' }, Object.keys(schema.shape))
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
      <FormError message={errors.root?.server?.message} />
      <FieldGroup className="gap-4">
        <FieldRow id="name" label="Nome do cartão" error={errors.name?.message}>
          <Input
            {...fieldA11y('name', errors.name?.message)}
            {...register('name')}
            maxLength={60}
            placeholder="Ex.: Nubank"
          />
        </FieldRow>
        <FieldRow id="limit" label="Limite" error={errors.limit?.message}>
          <Input
            {...fieldA11y('limit', errors.limit?.message)}
            {...register('limit')}
            inputMode="decimal"
            placeholder="0,00"
          />
        </FieldRow>
        <div className="grid gap-4 sm:grid-cols-2">
          <FieldRow
            id="closing_day"
            label="Dia do fechamento"
            error={errors.closing_day?.message}
            description="Compras feitas a partir deste dia vão para a fatura seguinte."
          >
            <Input
              {...fieldA11y('closing_day', errors.closing_day?.message)}
              {...register('closing_day')}
              type="number"
              inputMode="numeric"
              min={1}
              max={31}
            />
          </FieldRow>
          <FieldRow
            id="due_day"
            label="Dia do vencimento"
            error={errors.due_day?.message}
            description="Dia em que a fatura vence."
          >
            <Input
              {...fieldA11y('due_day', errors.due_day?.message)}
              {...register('due_day')}
              type="number"
              inputMode="numeric"
              min={1}
              max={31}
            />
          </FieldRow>
        </div>
      </FieldGroup>
      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
