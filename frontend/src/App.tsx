import { lazy } from 'react'
import { Link, Route, Routes } from 'react-router'

import { PageHeader } from '@/components/page'
import { AppLayout } from '@/components/layout/AppLayout'
import { Button } from '@/components/ui/button'

// Cada página vira um arquivo separado: o navegador só baixa o código da tela que for aberta.
const AnnualPage = lazy(() => import('@/features/annual/AnnualPage').then((module) => ({ default: module.AnnualPage })))
const CardsPage = lazy(() => import('@/features/cards/CardsPage').then((module) => ({ default: module.CardsPage })))
const CategoriesPage = lazy(() =>
  import('@/features/categories/CategoriesPage').then((module) => ({ default: module.CategoriesPage })),
)
const DashboardPage = lazy(() =>
  import('@/features/dashboard/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const GoalsPage = lazy(() => import('@/features/goals/GoalsPage').then((module) => ({ default: module.GoalsPage })))
const RecurringPage = lazy(() =>
  import('@/features/recurring/RecurringPage').then((module) => ({ default: module.RecurringPage })),
)
const SettingsPage = lazy(() =>
  import('@/features/settings/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)
const TransactionsPage = lazy(() =>
  import('@/features/transactions/TransactionsPage').then((module) => ({ default: module.TransactionsPage })),
)

function NotFoundPage() {
  return (
    <>
      <PageHeader title="Página não encontrada" description="O endereço digitado não existe." />
      <Button asChild className="self-start">
        <Link to="/">Voltar ao painel</Link>
      </Button>
    </>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="lancamentos" element={<TransactionsPage />} />
        <Route path="fixas" element={<RecurringPage />} />
        <Route path="cartoes" element={<CardsPage />} />
        <Route path="metas" element={<GoalsPage />} />
        <Route path="categorias" element={<CategoriesPage />} />
        <Route path="anual" element={<AnnualPage />} />
        <Route path="configuracoes" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
