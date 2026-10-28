import type {
  BudgetSettings,
  Card,
  CardInput,
  Category,
  CategoryInput,
  CategoryRule,
  CategoryRuleInput,
  ConfirmInput,
  Goal,
  GoalInput,
  Invoice,
  InvoiceImportDetail,
  InvoiceImportList,
  LineUpdate,
  Me,
  MonthSummary,
  RecurringInput,
  RecurringRule,
  Transaction,
  TransactionCreate,
  TransactionFilters,
  TransactionInput,
  YearSummary,
} from './types'

/** Erro da API com a mensagem pronta para o usuário e, quando houver, o erro de cada campo. */
export class ApiError extends Error {
  readonly status: number
  readonly fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

let onUnauthorized: (() => void) | null = null
const SESSION_CHECK_PATHS = new Set(['/auth/login', '/auth/me'])

/** Chamado quando uma rota protegida responde 401 (sessão expirada ou derrubada). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

type Query = Record<string, string | number | undefined>

function withQuery(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `${path}?${text}` : path
}

interface ErrorBody {
  detail?: unknown
  errors?: Array<{ field?: string | null; message?: string }>
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      // FormData (envio de arquivo) vai como está: o navegador define o Content-Type com o separador.
      headers: body === undefined || body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined || body instanceof FormData ? body : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Não foi possível falar com o servidor. Verifique sua conexão e tente de novo.')
  }
  if (response.status === 204) return undefined as T
  const data: unknown = await response.json().catch(() => null)
  if (response.ok) return data as T

  // Login errado e a checagem inicial de sessão respondem 401 sem que nenhuma sessão tenha expirado.
  if (response.status === 401 && !SESSION_CHECK_PATHS.has(path)) onUnauthorized?.()
  const errorBody = (data ?? {}) as ErrorBody
  const message =
    typeof errorBody.detail === 'string'
      ? errorBody.detail
      : `O servidor respondeu com um erro (${response.status}). Tente de novo em instantes.`
  const fieldErrors = Object.fromEntries(
    (errorBody.errors ?? [])
      .filter((error) => error.field && error.message)
      .map((error) => [error.field as string, error.message as string]),
  )
  throw new ApiError(response.status, message, fieldErrors)
}

const get = <T>(path: string, query?: Query) => request<T>('GET', withQuery(path, query))
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, body)
const put = <T>(path: string, body: unknown) => request<T>('PUT', path, body)
const remove = (path: string, query?: Query) => request<void>('DELETE', withQuery(path, query))

export const api = {
  auth: {
    login: (username: string, password: string) => post<Me>('/auth/login', { username, password }),
    logout: () => post<void>('/auth/logout'),
    me: () => get<Me>('/auth/me'),
  },
  categories: {
    list: () => get<Category[]>('/categories'),
    create: (body: CategoryInput) => post<Category>('/categories', body),
    update: (id: number, body: CategoryInput) => put<Category>(`/categories/${id}`, body),
    remove: (id: number) => remove(`/categories/${id}`),
  },
  cards: {
    list: () => get<Card[]>('/cards'),
    create: (body: CardInput) => post<Card>('/cards', body),
    update: (id: number, body: CardInput) => put<Card>(`/cards/${id}`, body),
    remove: (id: number) => remove(`/cards/${id}`),
    invoice: (id: number, month?: string) => get<Invoice>(`/cards/${id}/invoice`, { month }),
    forgetInvoicePassword: (id: number) => remove(`/cards/${id}/invoice-password`),
  },
  invoices: {
    list: () => get<InvoiceImportList>('/invoice-imports'),
    get: (id: number) => get<InvoiceImportDetail>(`/invoice-imports/${id}`),
    upload: (form: FormData) => post<InvoiceImportDetail>('/invoice-imports', form),
    confirm: (id: number) => post<InvoiceImportDetail>(`/invoice-imports/${id}/confirm`),
    remove: (id: number) => remove(`/invoice-imports/${id}`),
  },
  invoiceLines: {
    update: (id: number, body: LineUpdate) => put<InvoiceImportDetail>(`/invoice-lines/${id}`, body),
    include: (id: number) => post<InvoiceImportDetail>(`/invoice-lines/${id}/include`),
  },
  rules: {
    list: () => get<CategoryRule[]>('/category-rules'),
    create: (body: CategoryRuleInput) => post<CategoryRule>('/category-rules', body),
    update: (id: number, body: CategoryRuleInput) => put<CategoryRule>(`/category-rules/${id}`, body),
    remove: (id: number) => remove(`/category-rules/${id}`),
  },
  goals: {
    list: () => get<Goal[]>('/goals'),
    create: (body: GoalInput) => post<Goal>('/goals', body),
    update: (id: number, body: GoalInput) => put<Goal>(`/goals/${id}`, body),
    remove: (id: number) => remove(`/goals/${id}`),
  },
  transactions: {
    list: (filters: TransactionFilters) => get<Transaction[]>('/transactions', { ...filters }),
    create: (body: TransactionCreate) => post<Transaction[]>('/transactions', body),
    update: (id: number, body: TransactionInput) => put<Transaction>(`/transactions/${id}`, body),
    remove: (id: number, scope: 'one' | 'installments' = 'one') =>
      remove(`/transactions/${id}`, scope === 'one' ? undefined : { scope }),
  },
  recurring: {
    list: () => get<RecurringRule[]>('/recurring'),
    create: (body: RecurringInput) => post<RecurringRule>('/recurring', body),
    update: (id: number, body: RecurringInput) => put<RecurringRule>(`/recurring/${id}`, body),
    remove: (id: number) => remove(`/recurring/${id}`),
    confirm: (id: number, body: ConfirmInput) => post<Transaction>(`/recurring/${id}/confirm`, body),
  },
  budget: {
    get: () => get<BudgetSettings>('/budget-settings'),
    update: (body: BudgetSettings) => put<BudgetSettings>('/budget-settings', body),
  },
  summary: {
    month: (month: string) => get<MonthSummary>('/summary/month', { month }),
    year: (year: number) => get<YearSummary>('/summary/year', { year }),
  },
}
