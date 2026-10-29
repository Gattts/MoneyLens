import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { PageHeader, SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/auth-context'
import { api } from '@/lib/api'
import { USER_STATUS_LABELS } from '@/lib/labels'
import { useRefreshData, useUsers } from '@/lib/queries'
import type { AdminUser, Invite, UserCreateInput } from '@/lib/types'

import { expiryLabel } from './expiry'
import { InviteCard } from './InviteCard'
import { NewUserDialog } from './NewUserDialog'

type Pending = { kind: 'invite' | 'remove'; target: AdminUser }

function statusLabel(user: AdminUser): string {
  const label = USER_STATUS_LABELS[user.status]
  return user.status === 'pending' ? `${label} (convite vale até ${expiryLabel(user.invite_expires_at)})` : label
}

export function UsersPage() {
  const users = useUsers()
  const { user: me } = useAuth()
  const refresh = useRefreshData()
  const [creating, setCreating] = useState(false)
  const [invite, setInvite] = useState<Invite | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)

  async function create(body: UserCreateInput) {
    setInvite(await api.admin.users.create(body))
    setCreating(false)
    void refresh()
  }

  async function confirmPending() {
    if (!pending) return
    try {
      if (pending.kind === 'invite') setInvite(await api.admin.users.invite(pending.target.id))
      else {
        await api.admin.users.remove(pending.target.id)
        toast.success(`“${pending.target.username}” excluído.`)
      }
      setPending(null)
      void refresh()
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : 'Não foi possível concluir.')
    }
  }

  return (
    <>
      <PageHeader
        title="Usuários"
        description="Cadastre pessoas e envie o código de convite. Cada uma vê só os próprios dados."
        actions={
          <Button onClick={() => setCreating(true)}>
            <PlusIcon /> Novo usuário
          </Button>
        }
      />
      {invite && <InviteCard invite={invite} onClose={() => setInvite(null)} />}
      <SectionCard title="Contas">
        {users.isError ? (
          <QueryError error={users.error} onRetry={() => void users.refetch()} />
        ) : users.isPending ? (
          <LoadingBlock rows={3} />
        ) : (
          <ul className="flex flex-col divide-y">
            {users.data.map((user) => {
              const self = user.username === me.username
              return (
                <li
                  key={user.id}
                  aria-label={user.username}
                  className="flex flex-wrap items-center justify-between gap-2 py-2"
                >
                  <span className="min-w-0">
                    <span className="flex items-center gap-2 font-medium">
                      {user.username}
                      {user.is_admin && <Badge variant="secondary">Administrador</Badge>}
                    </span>
                    <span className="text-sm text-muted-foreground">{statusLabel(user)}</span>
                  </span>
                  <span className="flex flex-wrap gap-2">
                    {!self && (
                      <Button size="sm" variant="outline" onClick={() => setPending({ kind: 'invite', target: user })}>
                        Gerar novo convite
                      </Button>
                    )}
                    {!self && user.status !== 'active' && (
                      <Button size="sm" variant="ghost" onClick={() => setPending({ kind: 'remove', target: user })}>
                        Excluir
                      </Button>
                    )}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </SectionCard>
      <NewUserDialog open={creating} onOpenChange={setCreating} onSubmit={create} />
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title={pending?.kind === 'invite' ? 'Gerar novo convite?' : 'Excluir usuário?'}
        description={
          pending?.kind === 'invite'
            ? 'A senha atual dessa pessoa deixa de funcionar e as sessões abertas dela são encerradas.'
            : 'A conta ainda não foi ativada; o pacote padrão criado para ela também é apagado.'
        }
        actions={[
          {
            label: pending?.kind === 'invite' ? 'Gerar convite' : 'Excluir',
            destructive: pending?.kind === 'remove',
            onConfirm: confirmPending,
          },
        ]}
      />
    </>
  )
}
