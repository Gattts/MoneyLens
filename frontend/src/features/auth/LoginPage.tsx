import { zodResolver } from '@hookform/resolvers/zod'
import { WalletIcon } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { FieldRow, FormError, SubmitButton } from '@/components/form'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FieldGroup } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { fieldA11y, showServerErrors } from '@/lib/forms'

const schema = z.object({
  username: z.string().trim().min(1, 'Informe o usuário.'),
  password: z.string().min(1, 'Informe a senha.'),
})
type LoginValues = z.infer<typeof schema>

interface LoginPageProps {
  onLogin: (username: string, password: string) => Promise<unknown>
  notice?: string
}

export function LoginPage({ onLogin, notice }: LoginPageProps) {
  const { register, handleSubmit, setError, formState } = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: '', password: '' },
  })
  const { errors, isSubmitting } = formState

  async function submit(values: LoginValues) {
    try {
      await onLogin(values.username, values.password)
    } catch (error) {
      showServerErrors(error, setError)
    }
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <WalletIcon className="size-5" aria-hidden />
          </div>
          <CardTitle className="text-xl">Financeiro</CardTitle>
          <CardDescription>Entre para acompanhar seu dinheiro.</CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={handleSubmit(submit)} className="flex flex-col gap-4">
            <FormError message={errors.root?.server?.message ?? notice} />
            <FieldGroup className="gap-4">
              <FieldRow id="username" label="Usuário" error={errors.username?.message}>
                <Input
                  {...fieldA11y('username', errors.username?.message)}
                  {...register('username')}
                  autoComplete="username"
                  autoFocus
                />
              </FieldRow>
              <FieldRow id="password" label="Senha" error={errors.password?.message}>
                <Input
                  {...fieldA11y('password', errors.password?.message)}
                  {...register('password')}
                  type="password"
                  autoComplete="current-password"
                  maxLength={128}
                />
              </FieldRow>
            </FieldGroup>
            <SubmitButton submitting={isSubmitting} pendingText="Entrando…" className="w-full">
              Entrar
            </SubmitButton>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
