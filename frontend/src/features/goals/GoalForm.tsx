import { zodResolver } from '@hookform/resolvers/zod'
import type { BaseSyntheticEvent } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { centsToInput, parseMoneyToCents } from '@/lib/money'
import type { Goal, GoalInput } from '@/lib/types'
import { MAX_DATE, MIN_DATE, dateField, moneyField } from '@/lib/validation'

const schema = z.object({
  name: z.string().trim().min(1, 'Informe o nome da meta.').max(80, 'Use no máximo 80 caracteres.'),
  icon: z.string().trim().max(16, 'Use um emoji ou poucos caracteres.'),
  target: moneyField({ emptyMessage: 'Informe o valor que quer juntar.' }),
  target_date: z.union([z.literal(''), dateField()]),
})
type Values = z.infer<typeof schema>

interface GoalFormProps {
  initial?: Goal
  onSubmit: (body: GoalInput) => Promise<unknown>
  onCancel: () => void
}

export function GoalForm({ initial, onSubmit, onCancel }: GoalFormProps) {
  const { register, handleSubmit, setError, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: initial?.name ?? '',
      icon: initial?.icon ?? '🎯',
      target: initial ? centsToInput(initial.target_cents) : '',
      target_date: initial?.target_date ?? '',
    },
  })
  const { errors, isSubmitting } = formState

  async function submit(values: Values, event?: BaseSyntheticEvent) {
    // Data incompleta chega como "" (igual a vazio); só o navegador sabe a diferença.
    const form = event?.target as HTMLFormElement | undefined
    const dateInput = form?.elements.namedItem('target_date') as HTMLInputElement | null | undefined
    if (dateInput?.validity.badInput) {
      setError('target_date', { message: 'Data incompleta. Preencha dia, mês e ano ou apague o campo.' })
      return
    }
    try {
      await onSubmit({
        name: values.name,
        icon: values.icon,
        target_cents: parseMoneyToCents(values.target) ?? 0,
        target_date: values.target_date || null,
        archived: initial?.archived ?? false,
      })
    } catch (error) {
      showServerErrors(error, setError, { target_cents: 'target' }, Object.keys(schema.shape))
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
      <FormError message={errors.root?.server?.message} />
      <FieldGroup className="gap-4">
        <div className="grid gap-4 sm:grid-cols-[6rem_1fr]">
          <FieldRow id="icon" label="Ícone" error={errors.icon?.message}>
            <Input {...fieldA11y('icon', errors.icon?.message)} {...register('icon')} maxLength={16} />
          </FieldRow>
          <FieldRow id="name" label="Nome da meta" error={errors.name?.message}>
            <Input
              {...fieldA11y('name', errors.name?.message)}
              {...register('name')}
              maxLength={80}
              placeholder="Ex.: Reserva de emergência"
            />
          </FieldRow>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <FieldRow id="target" label="Valor a juntar" error={errors.target?.message}>
            <Input
              {...fieldA11y('target', errors.target?.message)}
              {...register('target')}
              inputMode="decimal"
              placeholder="0,00"
            />
          </FieldRow>
          <FieldRow id="target_date" label="Até quando (opcional)" error={errors.target_date?.message}>
            <Input
              {...fieldA11y('target_date', errors.target_date?.message)}
              {...register('target_date')}
              type="date"
              min={MIN_DATE}
              max={MAX_DATE}
            />
          </FieldRow>
        </div>
      </FieldGroup>
      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
