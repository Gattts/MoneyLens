import { zodResolver } from '@hookform/resolvers/zod'
import { SparklesIcon } from 'lucide-react'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { centsToInput, parseMoneyToCents } from '@/lib/money'
import { useLimitSuggestion } from '@/lib/queries'
import type { Category, LimitInput, SpendingLimit } from '@/lib/types'
import { moneyField } from '@/lib/validation'

import { NO_HISTORY, suggestionText } from './limit-labels'

const schema = z.object({
  category_id: z.string().min(1, 'Escolha a categoria.'),
  amount: moneyField({ emptyMessage: 'Informe o valor do teto.' }),
})
type Values = z.infer<typeof schema>

interface LimitFormProps {
  initial?: SpendingLimit
  categories: Category[] // as que podem ganhar teto (de despesa, ativas e sem teto)
  onSubmit: (body: LimitInput) => Promise<unknown>
  onCancel: () => void
}

export function LimitForm({ initial, categories, onSubmit, onCancel }: LimitFormProps) {
  const { control, register, handleSubmit, setError, setValue, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      category_id: initial ? String(initial.category_id) : '',
      amount: initial ? centsToInput(initial.amount_cents) : '',
    },
  })
  const { errors, isSubmitting } = formState
  const chosen = useWatch({ control, name: 'category_id' })
  const suggestion = useLimitSuggestion(chosen ? Number(chosen) : null)
  const hint = suggestion.data ? suggestionText(suggestion.data) : null

  async function submit(values: Values) {
    try {
      await onSubmit({ category_id: Number(values.category_id), amount_cents: parseMoneyToCents(values.amount) ?? 0 })
    } catch (error) {
      showServerErrors(error, setError, { amount_cents: 'amount' }, Object.keys(schema.shape))
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
      <FormError message={errors.root?.server?.message} />
      <FieldGroup className="gap-4">
        {initial ? (
          <p className="text-sm">
            Categoria: <span className="font-medium">{`${initial.icon} ${initial.name}`.trim()}</span>
          </p>
        ) : (
          <FieldRow id="category_id" label="Categoria" error={errors.category_id?.message}>
            <NativeSelect {...fieldA11y('category_id', errors.category_id?.message)} {...register('category_id')}>
              <NativeSelectOption value="">Escolha…</NativeSelectOption>
              {categories.map((category) => (
                <NativeSelectOption key={category.id} value={String(category.id)}>
                  {`${category.icon} ${category.name}`.trim()}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FieldRow>
        )}
        <FieldRow id="amount" label="Valor do teto" error={errors.amount?.message}>
          <Input
            {...fieldA11y('amount', errors.amount?.message)}
            {...register('amount')}
            inputMode="decimal"
            placeholder="0,00"
          />
        </FieldRow>
        {suggestion.data &&
          (hint && suggestion.data.suggested_cents !== null ? (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/40 p-3 text-sm">
              <span>{hint}</span>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  setValue('amount', centsToInput(suggestion.data.suggested_cents as number), { shouldValidate: true })
                }
              >
                <SparklesIcon /> Usar sugestão
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{NO_HISTORY}</p>
          ))}
      </FieldGroup>
      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
