import { CopyIcon } from 'lucide-react'
import { toast } from 'sonner'

import { SectionCard } from '@/components/page'
import { Button } from '@/components/ui/button'
import type { Invite } from '@/lib/types'

import { expiryLabel } from './expiry'

/** Mostra o código uma única vez, com o texto pronto para enviar à pessoa. */
export function InviteCard({ invite, onClose }: { invite: Invite; onClose: () => void }) {
  const message =
    `Acesse ${window.location.origin}, clique em "Primeiro acesso" e use o usuário ${invite.user.username} ` +
    `e o código ${invite.code}. O código vale até ${expiryLabel(invite.user.invite_expires_at)}.`

  async function copy() {
    try {
      await navigator.clipboard.writeText(message)
      toast.success('Texto copiado.')
    } catch {
      toast.error('Não foi possível copiar. Selecione o texto e copie à mão.')
    }
  }

  return (
    <SectionCard
      title={`Convite para ${invite.user.username}`}
      description="Este código não aparece de novo. Envie o texto abaixo para a pessoa."
    >
      <p className="font-mono text-2xl font-semibold tracking-widest">{invite.code}</p>
      <p className="rounded-lg bg-muted p-3 text-sm">{message}</p>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void copy()}>
          <CopyIcon /> Copiar
        </Button>
        <Button variant="outline" onClick={onClose}>
          Fechar
        </Button>
      </div>
    </SectionCard>
  )
}
