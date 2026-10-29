import { BellRingIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAlerts } from '@/lib/queries'

import { useAlertsPanel } from './alerts-context'
import { alertMessage } from './limit-labels'

const SHOWN = 3

/** Aviso no topo do Painel com os alertas de teto ainda não lidos. */
export function AlertBanner() {
  const alerts = useAlerts()
  const panel = useAlertsPanel()
  const unread = (alerts.data?.items ?? []).filter((item) => item.read_at === null).slice(0, SHOWN)
  if (unread.length === 0) return null
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex items-start gap-3">
        <BellRingIcon className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
        <ul className="flex flex-col gap-1 text-sm">
          {unread.map((item) => (
            <li key={item.id}>{alertMessage(item)}</li>
          ))}
        </ul>
      </div>
      <Button variant="outline" size="sm" onClick={panel.open}>
        Ver todos
      </Button>
    </div>
  )
}
