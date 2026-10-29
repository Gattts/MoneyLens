import { BellIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAlerts } from '@/lib/queries'

import { useAlertsPanel } from './alerts-context'

export function AlertBell() {
  const alerts = useAlerts()
  const panel = useAlertsPanel()
  const unread = alerts.data?.unread ?? 0
  return (
    <Button variant="ghost" size="icon" aria-label="Alertas de teto" className="relative" onClick={panel.open}>
      <BellIcon aria-hidden />
      {unread > 0 && (
        <span className="absolute -top-0.5 -right-0.5 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[0.625rem] font-semibold leading-4 text-white">
          {unread}
        </span>
      )}
    </Button>
  )
}
