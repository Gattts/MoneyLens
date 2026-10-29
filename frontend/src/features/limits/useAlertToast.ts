import { useEffect } from 'react'
import { toast } from 'sonner'

import { useAlerts } from '@/lib/queries'

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

/** Aviso rápido ao entrar no app, uma vez por sessão, se houver alertas de teto não lidos. */
export function useAlertToast(): void {
  const unread = useAlerts().data?.unread ?? 0
  useEffect(() => {
    if (unread === 0 || alreadyWarned()) return
    markWarned()
    toast(unread === 1 ? 'Você tem 1 alerta de teto' : `Você tem ${unread} alertas de teto`)
  }, [unread])
}
