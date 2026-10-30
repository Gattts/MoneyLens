import { useEffect, useRef } from 'react'
import { toast } from 'sonner'

import { useAlerts } from '@/lib/queries'

import { alertMessage } from './limit-labels'

const STORAGE_KEY = 'alertas-avisados'
let warnedWithoutStorage = false // quando o navegador bloqueia o sessionStorage

function alreadyWarned(): boolean {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return warnedWithoutStorage
  }
}

function markWarned(): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, '1')
  } catch {
    warnedWithoutStorage = true
  }
}

/**
 * Aviso rápido dos alertas de teto: ao entrar no app (uma vez por sessão, se houver não lidos) e sempre que um
 * alerta novo aparece durante a sessão (por exemplo, logo depois de um lançamento), com o texto dele.
 */
export function useAlertToast(): void {
  const data = useAlerts().data
  const previous = useRef<number | null>(null)
  useEffect(() => {
    if (!data) return
    const before = previous.current
    previous.current = data.unread
    if (before === null) {
      if (data.unread === 0 || alreadyWarned()) return
      markWarned()
      toast(data.unread === 1 ? 'Você tem 1 alerta de teto' : `Você tem ${data.unread} alertas de teto`)
      return
    }
    const newest = data.items.find((item) => item.read_at === null)
    if (data.unread > before && newest) toast(alertMessage(newest))
  }, [data])
}
