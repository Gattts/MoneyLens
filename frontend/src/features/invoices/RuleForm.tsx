import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { SegmentedControl } from '@/components/SegmentedControl'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { MATCH_TYPE_LABELS } from '@/lib/labels'
import type { Category, CategoryRule, CategoryRuleInput, MatchType } from '@/lib/types'

const schema = z.object({
  pattern: z.string().trim().min(2, 'Use pelo menos 2 caracteres.').max(80, 'Use no máximo 80 caracteres.'),
  match_type: z.enum(['exact', 'contains']),
  category_id: z.string().min(1, 'Escolha a categoria.'),
})
type Values = z.infer<typeof schema>

const MATCH_OPTIONS = (Object.keys(MATCH_TYPE_LABELS) as MatchType[]).map((value) => ({
  value,
  label: MATCH_TYPE_LABELS[value],
}))

interface RuleFormProps {
  initial?: CategoryRule
  categories: Category[]
  onSubmit: (body: CategoryRuleInput) => Promise<unknown>
  onCancel: () => void
}

export function RuleForm({ initial, categories, onSubmit, onCancel }: RuleFormProps) {
  const { register, handleSubmit, setError, setValue, control, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      pattern: initial?.pattern ?? '',
      match_type: initial?.match_type ?? 'contains',
      category_id: initial ? String(initial.category_id) : '',
    },
  })
  const { errors, isSubmitting } = formState
  const matchType = useWatch({ control, name: 'match_type' })
  const options = categories.filter(
    (item) => item.kind === 'expense' && (!item.archived || item.id === initial?.category_id),
  )

  async function submit(values: Values) {
    try {
      await onSubmit({
        pattern: values.pattern,
        match_type: values.match_type,
        category_id: Number(values.category_id),
      })
    } catch (error) {
      showServerErrors(error, setError, {}, Object.keys(schema.shape))
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
      <FormError message={errors.root?.server?.message} />
      <FieldGroup className="gap-4">
        <FieldRow
          id="pattern"
          label="Texto"
          error={errors.pattern?.message}
          description="Como aparece na fatura (maiúsculas e acentos não importam). Ex.: UBER, PADARIA DO ZE"
        >
          <Input {...fieldA11y('pattern', errors.pattern?.message)} {...register('pattern')} maxLength={80} />
        </FieldRow>
        <SegmentedControl
          label="Comparação"
          name="match_type"
          value={matchType}
          options={MATCH_OPTIONS}
          onChange={(value) => setValue('match_type', value)}
        />
        <FieldRow id="category_id" label="Categoria" error={errors.category_id?.message}>
          <NativeSelect
            className="w-full"
            {...fieldA11y('category_id', errors.category_id?.message)}
            {...register('category_id')}
          >
            <NativeSelectOption value="">Escolha…</NativeSelectOption>
            {options.map((item) => (
              <NativeSelectOption key={item.id} value={String(item.id)}>
                {item.icon} {item.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </FieldRow>
      </FieldGroup>
      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
