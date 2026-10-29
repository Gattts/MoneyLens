import { useQueryClient } from '@tanstack/react-query'
import { useMemo, useState, type ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/dates'
import { keys, useAlerts } from '@/lib/queries'

import { AlertsPanelContext } from './alerts-context'
import { alertMessage } from './limit-labels'

/** Um painel lateral só, montado uma vez no layout; o sino (computador e celular) e o Painel o abrem. */
export function AlertsProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [fresh, setFresh] = useState<Set<number>>(new Set())
  const alerts = useAlerts()
  const queryClient = useQueryClient()

  // Ao abrir, os não lidos ficam marcados como "Novo" nesta abertura e viram lidos no servidor.
  const context = useMemo(
    () => ({
      open: () => {
        const unread = (alerts.data?.items ?? []).filter((item) => item.read_at === null).map((item) => item.id)
        setFresh(new Set(unread))
        setOpen(true)
        if (unread.length > 0) {
          void api.alerts.read().then((data) => queryClient.setQueryData(keys.alerts, data))
        }
      },
    }),
    [alerts.data, queryClient],
  )
  const items = alerts.data?.items ?? []

  return (
    <AlertsPanelContext.Provider value={context}>
      {children}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="flex w-80 flex-col gap-4 p-4 sm:w-96">
          <SheetHeader className="p-0">
            <SheetTitle>Alertas de teto</SheetTitle>
            <SheetDescription>Os avisos mais recentes dos seus tetos de gasto.</SheetDescription>
          </SheetHeader>
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhum alerta ainda.</p>
          ) : (
            <ul className="flex flex-col gap-3 overflow-y-auto">
              {items.map((item) => (
                <li key={item.id} className="flex flex-col gap-1 rounded-lg border p-3 text-sm">
                  <span>{alertMessage(item)}</span>
                  <span className="flex items-center gap-2 text-xs text-muted-foreground">
                    {formatDate(item.created_at.slice(0, 10))}
                    {fresh.has(item.id) && <Badge variant="secondary">Novo</Badge>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </SheetContent>
      </Sheet>
    </AlertsPanelContext.Provider>
  )
}
