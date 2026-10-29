import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormActions, FormError } from '@/components/form'
import { FormDialog } from '@/components/FormDialog'
import { Input } from '@/components/ui/input'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import type { UserCreateInput } from '@/lib/types'

const schema = z.object({ username: z.string().trim().min(1, 'Informe o nome de usuário.') })
type Values = z.infer<typeof schema>

export function NewUserDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (body: UserCreateInput) => Promise<unknown>
}) {
  const { register, handleSubmit, setError, formState, reset } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { username: '' },
  })
  const { errors, isSubmitting } = formState

  async function submit(values: Values) {
    try {
      await onSubmit({ username: values.username })
      reset()
    } catch (error) {
      showServerErrors(error, setError, {}, ['username'])
    }
  }

  return (
    <FormDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Novo usuário"
      description="A pessoa recebe um código de convite e escolhe a própria senha no primeiro acesso."
    >
      <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-5">
        <FormError message={errors.root?.server?.message} />
        <FieldRow
          id="new-username"
          label="Nome de usuário"
          error={errors.username?.message}
          description="De 3 a 50 caracteres: letras, números, ponto, hífen ou sublinhado, sem espaços."
        >
          <Input {...fieldA11y('new-username', errors.username?.message)} {...register('username')} maxLength={50} />
        </FieldRow>
        <FormActions submitting={isSubmitting} onCancel={() => onOpenChange(false)} />
      </form>
    </FormDialog>
  )
}
