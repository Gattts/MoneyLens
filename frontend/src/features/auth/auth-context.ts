import { createContext, useContext } from 'react'

import type { Me } from '@/lib/types'

export interface AuthContextValue {
  user: Me
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth precisa estar dentro de <AuthGate>.')
  return value
}
