import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { SegmentedControl } from '@/components/SegmentedControl'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import { BUCKET_HINTS, BUCKET_LABELS, BUCKETS, KIND_LABELS } from '@/lib/labels'
import type { Category, CategoryInput } from '@/lib/types'

const schema = z
  .object({
    kind: z.enum(['expense', 'income']),
    name: z.string().trim().min(1, 'Informe o nome da categoria.').max(60, 'Use no máximo 60 caracteres.'),
    icon: z.string().trim().max(16, 'Use um emoji ou poucos caracteres.'),
    default_bucket: z.enum([...BUCKETS, '']),
    description: z.string().trim().max(300, 'Use no máximo 300 caracteres.'),
  })
  .superRefine((values, ctx) => {
    if (values.kind === 'expense' && !values.default_bucket)
      ctx.addIssue({ code: 'custom', path: ['default_bucket'], message: 'Escolha o grupo do orçamento.' })
  })
type Values = z.infer<typeof schema>

const KIND_OPTIONS = [
  { value: 'expense', label: KIND_LABELS.expense },
  { value: 'income', label: KIND_LABELS.income },
] as const

interface CategoryFormProps {
  initial?: Category
  onSubmit: (body: CategoryInput) => Promise<unknown>
  onCancel: () => void
}

export function CategoryForm({ initial, onSubmit, onCancel }: CategoryFormProps) {
  const { register, handleSubmit, setValue, setError, control, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      kind: initial?.kind ?? 'expense',
      name: initial?.name ?? '',
      icon: initial?.icon ?? '',
      default_bucket: initial?.default_bucket ?? '',
      description: initial?.description ?? '',
    },
  })
  const { errors, isSubmitting } = formState
  const [kind, bucket] = useWatch({ control, name: ['kind', 'default_bucket'] })

  async function submit(values: Values) {
    try {
      await onSubmit({
        kind: values.kind,
        name: values.name,
        icon: values.icon,
        default_bucket: values.kind === 'expense' && values.default_bucket ? values.default_bucket : null,
        description: values.description,
        archived: initial?.archived ?? false,
      })
    } catch (error) {
      showServerErrors(error, setError, {}, Object.keys(schema.shape))
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
      <FormError message={errors.root?.server?.message} />
      <FieldGroup className="gap-4">
        <SegmentedControl
          label="Tipo"
          name="kind"
          value={kind}
          options={KIND_OPTIONS}
          onChange={(next) => {
            setValue('kind', next)
            if (next === 'income') setValue('default_bucket', '')
          }}
        />
        <div className="grid gap-4 sm:grid-cols-[6rem_1fr]">
          <FieldRow id="icon" label="Ícone" error={errors.icon?.message}>
            <Input {...fieldA11y('icon', errors.icon?.message)} {...register('icon')} maxLength={16} placeholder="🛒" />
          </FieldRow>
          <FieldRow id="name" label="Nome" error={errors.name?.message}>
            <Input {...fieldA11y('name', errors.name?.message)} {...register('name')} maxLength={60} />
          </FieldRow>
        </div>
        {kind === 'expense' && (
          <FieldRow
            id="default_bucket"
            label="Grupo do orçamento"
            error={errors.default_bucket?.message}
            description={bucket ? BUCKET_HINTS[bucket] : 'Grupo usado por padrão nos lançamentos desta categoria.'}
          >
            <NativeSelect
              className="w-full"
              {...fieldA11y('default_bucket', errors.default_bucket?.message)}
              {...register('default_bucket')}
            >
              <NativeSelectOption value="">Escolha…</NativeSelectOption>
              {BUCKETS.map((value) => (
                <NativeSelectOption key={value} value={value}>
                  {BUCKET_LABELS[value]}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FieldRow>
        )}
        <FieldRow id="description" label="O que entra aqui (opcional)" error={errors.description?.message}>
          <Textarea
            {...fieldA11y('description', errors.description?.message)}
            {...register('description')}
            maxLength={300}
            rows={2}
          />
        </FieldRow>
      </FieldGroup>
      <FormActions submitting={isSubmitting} onCancel={onCancel} />
    </form>
  )
}
