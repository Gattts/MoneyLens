import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormError, SubmitButton } from '@/components/form'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { BUCKET_HINTS } from '@/lib/labels'
import type { BudgetSettings } from '@/lib/types'
import { cn } from '@/lib/utils'
import { integerText } from '@/lib/validation'

const percent = integerText(0, 100, 'Use um número inteiro de 0 a 100.')
const schema = z.object({ needs_pct: percent, wants_pct: percent, savings_pct: percent })
type Values = z.infer<typeof schema>

const FIELDS = [
  { name: 'needs_pct', label: 'Necessidades (%)', hint: BUCKET_HINTS.needs },
  { name: 'wants_pct', label: 'Desejos (%)', hint: BUCKET_HINTS.wants },
  { name: 'savings_pct', label: 'Poupança (%)', hint: BUCKET_HINTS.savings },
] as const

function sumStatus(total: number): { text: string; ok: boolean } {
  if (total === 100) return { text: 'Tudo certo: 100%', ok: true }
  return total < 100 ? { text: `Faltam ${100 - total}%`, ok: false } : { text: `Passou ${total - 100}%`, ok: false }
}

interface BudgetSettingsFormProps {
  initial: BudgetSettings
  onSubmit: (settings: BudgetSettings) => Promise<unknown>
}

export function BudgetSettingsForm({ initial, onSubmit }: BudgetSettingsFormProps) {
  const { register, handleSubmit, setError, control, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      needs_pct: String(initial.needs_pct),
      wants_pct: String(initial.wants_pct),
      savings_pct: String(initial.savings_pct),
    },
  })
  const { errors, isSubmitting } = formState
  const values = useWatch({ control, name: ['needs_pct', 'wants_pct', 'savings_pct'] })
  const total = values.reduce((sum, value) => sum + (Number.parseInt(value, 10) || 0), 0)
  const status = sumStatus(total)

  async function submit(form: Values) {
    const settings = {
      needs_pct: Number(form.needs_pct),
      wants_pct: Number(form.wants_pct),
      savings_pct: Number(form.savings_pct),
    }
    if (settings.needs_pct + settings.wants_pct + settings.savings_pct !== 100) {
      setError('root.server', { message: 'Os percentuais precisam somar 100%.' })
      return
    }
    try {
      await onSubmit(settings)
    } catch (error) {
      showServerErrors(error, setError, {}, Object.keys(schema.shape))
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
      <FormError message={errors.root?.server?.message} />
      <FieldGroup className="gap-4 sm:grid sm:grid-cols-3">
        {FIELDS.map((field) => (
          <FieldRow
            key={field.name}
            id={field.name}
            label={field.label}
            error={errors[field.name]?.message}
            description={field.hint}
          >
            <Input
              {...fieldA11y(field.name, errors[field.name]?.message)}
              {...register(field.name)}
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
            />
          </FieldRow>
        ))}
      </FieldGroup>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p aria-live="polite" className={cn('text-sm font-medium', status.ok ? 'text-emerald-600' : 'text-amber-600')}>
          {status.text}
        </p>
        <SubmitButton submitting={isSubmitting} />
      </div>
    </form>
  )
}
