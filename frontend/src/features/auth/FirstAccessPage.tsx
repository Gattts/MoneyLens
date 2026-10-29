import { zodResolver } from '@hookform/resolvers/zod'
import { KeyRoundIcon } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router'
import { z } from 'zod'

import { FieldRow, FormError, SubmitButton } from '@/components/form'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { fieldA11y, showServerErrors } from '@/lib/forms'
import type { ActivateInput } from '@/lib/types'

const PASSWORD_RULE = 'Use de 8 a 128 caracteres.'
const schema = z
  .object({
    username: z.string().trim().min(1, 'Informe o usuário.'),
    code: z.string().trim().min(1, 'Informe o código de convite.'),
    password: z.string().min(8, PASSWORD_RULE).max(128, PASSWORD_RULE),
    repeat: z.string(),
  })
  .refine((values) => values.password === values.repeat, { message: 'As senhas não conferem.', path: ['repeat'] })
type Values = z.infer<typeof schema>

/** Primeiro acesso: com o usuário e o código que o administrador enviou, a pessoa escolhe a própria senha. */
export function FirstAccessPage({ onActivate }: { onActivate: (body: ActivateInput) => Promise<unknown> }) {
  const { register, handleSubmit, setError, formState } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { username: '', code: '', password: '', repeat: '' },
  })
  const { errors } = formState
  const sending = useSingleFlight()

  function submit(values: Values) {
    void sending.run(async () => {
      try {
        await onActivate({ username: values.username, code: values.code, password: values.password })
      } catch (error) {
        showServerErrors(error, setError, {}, ['username', 'code', 'password'])
      }
    })
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <KeyRoundIcon className="size-5" aria-hidden />
          </div>
          <CardTitle className="text-xl">Primeiro acesso</CardTitle>
          <CardDescription>Use o usuário e o código de convite que você recebeu e escolha a sua senha.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-4">
            <FormError message={errors.root?.server?.message} />
            <FieldGroup className="gap-4">
              <FieldRow id="username" label="Usuário" error={errors.username?.message}>
                <Input
                  {...fieldA11y('username', errors.username?.message)}
                  {...register('username')}
                  autoComplete="username"
                  autoFocus
                />
              </FieldRow>
              <FieldRow id="code" label="Código de convite" error={errors.code?.message}>
                <Input
                  {...fieldA11y('code', errors.code?.message)}
                  {...register('code')}
                  autoComplete="one-time-code"
                  placeholder="XXXX-XXXX"
                />
              </FieldRow>
              <FieldRow id="password" label="Nova senha" error={errors.password?.message}>
                <Input
                  {...fieldA11y('password', errors.password?.message)}
                  {...register('password')}
                  type="password"
                  autoComplete="new-password"
                  maxLength={128}
                />
              </FieldRow>
              <FieldRow id="repeat" label="Repita a senha" error={errors.repeat?.message}>
                <Input
                  {...fieldA11y('repeat', errors.repeat?.message)}
                  {...register('repeat')}
                  type="password"
                  autoComplete="new-password"
                  maxLength={128}
                />
              </FieldRow>
            </FieldGroup>
            <SubmitButton submitting={sending.pending} pendingText="Ativando…" className="w-full">
              Ativar conta
            </SubmitButton>
          </form>
          <Button asChild variant="link" className="self-center">
            <Link to="/">Voltar ao login</Link>
          </Button>
        </CardContent>
      </Card>
    </main>
  )
}
