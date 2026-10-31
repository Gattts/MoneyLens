import { zodResolver } from '@hookform/resolvers/zod'
import { SparklesIcon } from 'lucide-react'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { SegmentedControl } from '@/components/SegmentedControl'
import { Button } from '@/components/ui/button'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { centsToInput, formatCents, parseMoneyToCents } from '@/lib/money'
import { useLimitSuggestion } from '@/lib/queries'
import type { Category, LimitInput, SpendingLimit } from '@/lib/types'
import { moneyField } from '@/lib/validation'

import { type LimitBasis, NO_HISTORY, NO_INCOME, percentOf, suggestionText } from './limit-labels'

const BASIS_OPTIONS = [
  { value: 'amount', label: 'Valor (R$)' },
  { value: 'percent', label: '% da renda' },
] as const
const amountField = moneyField({ emptyMessage: 'Informe o valor do teto.' })
const PERCENT_MESSAGE = 'Informe uma porcentagem inteira de 1 a 100.'

const schema = z
  .object({
    category_id: z.string().min(1, 'Escolha a categoria.'),
    basis: z.enum(['amount', 'percent']),
    amount: z.string(),
    percent: z.string(),
  })
  .superRefine((values, ctx) => {
    if (values.basis === 'amount') {
      const checked = amountField.safeParse(values.amount)
      if (!checked.success) ctx.addIssue({ code: 'custom', path: ['amount'], message: checked.error.issues[0].message })
    } else if (parsePercent(values.percent) === null) {
      ctx.addIssue({ code: 'custom', path: ['percent'], message: PERCENT_MESSAGE })
    }
  })
type Values = z.infer<typeof schema>

function parsePercent(raw: string): number | null {
  if (!/^\d{1,3}$/.test(raw.trim())) return null
  const value = Number(raw.trim())
  return value >= 1 && value <= 100 ? value : null
}

interface LimitFormProps {
  initial?: SpendingLimit
  categories: Category[] // as que podem ganhar teto (de despesa, ativas e sem teto)
  onSubmit: (body: LimitInput) => Promise<unknown>
  onCancel: () => void
}

export function LimitForm({ initial, categories, onSubmit, onCancel }: LimitFormProps) {
  const percentLimit = initial?.income_percent != null
  const { control, register, handleSubmit, setError, setValue, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      category_id: initial ? String(initial.category_id) : '',
      basis: percentLimit ? 'percent' : 'amount',
      amount: initial && !percentLimit ? centsToInput(initial.amount_cents) : '',
      percent: initial?.income_percent != null ? String(initial.income_percent) : '',
    },
  })
  const { errors, isSubmitting } = formState
  const [chosen, basis, percent] = useWatch({ control, name: ['category_id', 'basis', 'percent'] })
  const suggestion = useLimitSuggestion(chosen ? Number(chosen) : null)
  const data = suggestion.data
  const hint = data ? suggestionText(data, basis) : null
  const typedPercent = parsePercent(percent)

  function applySuggestion() {
    if (!data || data.suggested_cents === null) return
    if (basis === 'amount') setValue('amount', centsToInput(data.suggested_cents), { shouldValidate: true })
    else if (data.suggested_percent !== null)
      setValue('percent', String(data.suggested_percent), { shouldValidate: true })
  }

  async function submit(values: Values) {
    const value: Pick<LimitInput, 'amount_cents' | 'income_percent'> =
      values.basis === 'amount'
        ? { amount_cents: parseMoneyToCents(values.amount) ?? 0 }
        : { income_percent: parsePercent(values.percent) ?? 0 }
    try {
      await onSubmit({ category_id: Number(values.category_id), ...value })
    } catch (error) {
      showServerErrors(
        error,
        setError,
        { amount_cents: 'amount', income_percent: 'percent' },
        Object.keys(schema.shape),
      )
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
        <SegmentedControl
          label="Forma do teto"
          name="basis"
          value={basis}
          options={BASIS_OPTIONS}
          onChange={(value: LimitBasis) => setValue('basis', value)}
        />
        {basis === 'amount' ? (
          <FieldRow id="amount" label="Valor do teto" error={errors.amount?.message}>
            <Input
              {...fieldA11y('amount', errors.amount?.message)}
              {...register('amount')}
              inputMode="decimal"
              placeholder="0,00"
            />
          </FieldRow>
        ) : (
          <FieldRow id="percent" label="Porcentagem da renda" error={errors.percent?.message}>
            <Input
              {...fieldA11y('percent', errors.percent?.message)}
              {...register('percent')}
              inputMode="numeric"
              placeholder="Ex.: 15"
              maxLength={3}
            />
          </FieldRow>
        )}
        {basis === 'percent' && data && (
          <p className="text-sm text-muted-foreground">
            {data.income_cents === 0
              ? NO_INCOME
              : typedPercent !== null &&
                `${typedPercent}% da renda prevista = ${formatCents(percentOf(data.income_cents, typedPercent))} neste mês`}
          </p>
        )}
        {data &&
          (hint ? (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/40 p-3 text-sm">
              <span>{hint}</span>
              <Button type="button" variant="outline" size="sm" onClick={applySuggestion}>
                <SparklesIcon /> Usar sugestão
              </Button>
            </div>
          ) : (
            data.suggested_cents === null && <p className="text-sm text-muted-foreground">{NO_HISTORY}</p>
          ))}
      </FieldGroup>
      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
