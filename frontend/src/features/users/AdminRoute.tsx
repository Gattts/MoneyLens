import type { ReactNode } from 'react'

import { NotFoundPage } from '@/components/NotFoundPage'
import { useAuth } from '@/features/auth/auth-context'

/** Páginas de administração: para os demais usuários, o endereço simplesmente não existe. */
export function AdminRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return user.is_admin ? children : <NotFoundPage />
}
