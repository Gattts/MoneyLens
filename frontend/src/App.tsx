import { lazy } from 'react'
import { Route, Routes } from 'react-router'

import { AppLayout } from '@/components/layout/AppLayout'
import { NotFoundPage } from '@/components/NotFoundPage'
import { AdminRoute } from '@/features/users/AdminRoute'

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
const InvoiceImportPage = lazy(() =>
  import('@/features/invoices/InvoiceImportPage').then((module) => ({ default: module.InvoiceImportPage })),
)
const InvoicesPage = lazy(() =>
  import('@/features/invoices/InvoicesPage').then((module) => ({ default: module.InvoicesPage })),
)
const RecurringPage = lazy(() =>
  import('@/features/recurring/RecurringPage').then((module) => ({ default: module.RecurringPage })),
)
const SettingsPage = lazy(() =>
  import('@/features/settings/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)
const UsersPage = lazy(() => import('@/features/users/UsersPage').then((module) => ({ default: module.UsersPage })))
const TransactionsPage = lazy(() =>
  import('@/features/transactions/TransactionsPage').then((module) => ({ default: module.TransactionsPage })),
)

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="lancamentos" element={<TransactionsPage />} />
        <Route path="fixas" element={<RecurringPage />} />
        <Route path="cartoes" element={<CardsPage />} />
        <Route path="faturas" element={<InvoicesPage />} />
        <Route path="faturas/:id" element={<InvoiceImportPage />} />
        <Route path="metas" element={<GoalsPage />} />
        <Route path="categorias" element={<CategoriesPage />} />
        <Route path="anual" element={<AnnualPage />} />
        <Route path="configuracoes" element={<SettingsPage />} />
        <Route
          path="usuarios"
          element={
            <AdminRoute>
              <UsersPage />
            </AdminRoute>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
