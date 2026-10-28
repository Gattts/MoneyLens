import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { api } from './api'
import type { Me, TransactionFilters } from './types'

export const keys = {
  me: ['me'] as const,
  categories: ['categories'] as const,
  cards: ['cards'] as const,
  invoice: (cardId: number, month: string | undefined) => ['cards', cardId, 'invoice', month ?? 'atual'] as const,
  goals: ['goals'] as const,
  transactions: (filters: TransactionFilters) => ['transactions', filters] as const,
  recurring: ['recurring'] as const,
  budget: ['budget'] as const,
  monthSummary: (month: string) => ['summary', 'month', month] as const,
  invoiceImports: ['invoice-imports'] as const,
  invoiceImport: (id: number) => ['invoice-imports', id] as const,
  rules: ['category-rules'] as const,
  yearSummary: (year: number) => ['summary', 'year', year] as const,
}

export const useMe = () =>
  useQuery<Me | null>({ queryKey: keys.me, queryFn: api.auth.me, retry: false, staleTime: Infinity })
// `enabled = false` adia a busca até o dado ser necessário (ex.: um diálogo ainda fechado).
export const useCategories = (enabled = true) =>
  useQuery({ queryKey: keys.categories, queryFn: api.categories.list, enabled })
export const useCards = (enabled = true) => useQuery({ queryKey: keys.cards, queryFn: api.cards.list, enabled })
export const useGoals = (enabled = true) => useQuery({ queryKey: keys.goals, queryFn: api.goals.list, enabled })
export const useRecurring = () => useQuery({ queryKey: keys.recurring, queryFn: api.recurring.list })
export const useBudgetSettings = () => useQuery({ queryKey: keys.budget, queryFn: api.budget.get })
export const useInvoiceImports = () => useQuery({ queryKey: keys.invoiceImports, queryFn: api.invoices.list })
export const useInvoiceImport = (id: number) =>
  useQuery({ queryKey: keys.invoiceImport(id), queryFn: () => api.invoices.get(id) })
export const useRules = () => useQuery({ queryKey: keys.rules, queryFn: api.rules.list })

export const useInvoice = (cardId: number, month: string | undefined) =>
  useQuery({
    queryKey: keys.invoice(cardId, month),
    queryFn: () => api.cards.invoice(cardId, month),
    placeholderData: keepPreviousData,
  })

export const useTransactions = (filters: TransactionFilters) =>
  useQuery({
    queryKey: keys.transactions(filters),
    queryFn: () => api.transactions.list(filters),
    placeholderData: keepPreviousData,
  })

export const useMonthSummary = (month: string) =>
  useQuery({
    queryKey: keys.monthSummary(month),
    queryFn: () => api.summary.month(month),
    placeholderData: keepPreviousData,
  })

export const useYearSummary = (year: number) =>
  useQuery({
    queryKey: keys.yearSummary(year),
    queryFn: () => api.summary.year(year),
    placeholderData: keepPreviousData,
  })

/**
 * Depois de salvar qualquer coisa, recarrega tudo que é calculado (totais, faturas, metas...).
 * O app é pequeno: recarregar tudo é barato e evita tela com número desatualizado.
 */
export function useRefreshData() {
  const queryClient = useQueryClient()
  return useCallback(
    () => queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== keys.me[0] }),
    [queryClient],
  )
}
