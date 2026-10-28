import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect, useState } from 'react'

import { QueryError } from '@/components/query-state'
import { Spinner } from '@/components/ui/spinner'
import { ApiError, api, setUnauthorizedHandler } from '@/lib/api'
import { keys, useMe } from '@/lib/queries'

import { AuthContext } from './auth-context'
import { LoginPage } from './LoginPage'

/** Mostra a tela de login enquanto não houver sessão; com sessão, libera o app. */
export function AuthGate({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const me = useMe()
  const [notice, setNotice] = useState<string>()

  useEffect(() => {
    setUnauthorizedHandler(() => {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== keys.me[0] })
      queryClient.setQueryData(keys.me, null)
      setNotice('Sua sessão expirou. Entre de novo para continuar.')
    })
    return () => setUnauthorizedHandler(null)
  }, [queryClient])

  if (me.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center" aria-busy="true">
        <Spinner className="size-6" />
      </div>
    )
  }
  const notLoggedIn = me.isError && me.error instanceof ApiError && me.error.status === 401
  if (me.isError && !notLoggedIn) {
    return (
      <div className="mx-auto flex min-h-svh max-w-md items-center p-4">
        <QueryError error={me.error} onRetry={() => void me.refetch()} />
      </div>
    )
  }
  if (!me.data) {
    return (
      <LoginPage
        notice={notice}
        onLogin={async (username, password) => {
          const user = await api.auth.login(username, password)
          setNotice(undefined)
          queryClient.setQueryData(keys.me, user)
        }}
      />
    )
  }

  async function logout() {
    await api.auth.logout().catch(() => undefined)
    queryClient.clear()
    queryClient.setQueryData(keys.me, null)
  }

  return <AuthContext.Provider value={{ user: me.data, logout }}>{children}</AuthContext.Provider>
}
