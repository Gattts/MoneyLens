/**
 * Formatos da API, derivados do contrato gerado a partir do backend (`npm run api:types`).
 * Se um schema do backend mudar, o TypeScript acusa aqui e em todo uso. Valores em centavos, datas ISO.
 */
import type { components } from './api-schema'

type Schemas = components['schemas']

export type Kind = Schemas['Kind']
export type Bucket = Schemas['Bucket']
export type PaymentMethod = Schemas['PaymentMethod']
export type InvoiceStatus = Schemas['InvoiceStatus']
export type ThermometerStatus = Schemas['Thermometer']

export type Me = Schemas['MeOut']
export type ActivateInput = Schemas['ActivateIn']
export type AdminUser = Schemas['UserOut']
export type UserStatus = AdminUser['status']
export type UserCreateInput = Schemas['UserCreateIn']
export type Invite = Schemas['InviteOut']

export type Category = Schemas['CategoryOut']
export type CategoryInput = Schemas['CategoryIn']

export type Card = Schemas['CardOut']
export type CardInput = Schemas['CardIn']
export type InvoiceSummary = Schemas['InvoiceSummary']
export type Invoice = Schemas['InvoiceOut']

export type Transaction = Schemas['TransactionOut']
export type TransactionInput = Schemas['TransactionIn']
export type TransactionCreate = Schemas['TransactionCreate']

export type Goal = Schemas['GoalOut']
export type GoalInput = Schemas['GoalIn']

export type RecurringRule = Schemas['RecurringOut']
export type RecurringInput = Schemas['RecurringIn']
export type ConfirmInput = Schemas['ConfirmIn']

export type BudgetSettings = Schemas['BudgetSettingsOut']

export type LineStatus = Schemas['LineStatus']
export type SkipReason = Schemas['SkipReason']
export type ImportSource = Schemas['ImportSource']
export type PaymentSource = Schemas['PaymentSource']
export type Forecast = Schemas['ForecastOut']
export type CategoryForecast = Schemas['CategoryForecast']
export type ForecastModelInfo = Schemas['ForecastModelOut']
export type CardPayment = Schemas['CardPaymentOut']
export type CardPaymentInput = Schemas['CardPaymentIn']
export type LinePaymentInput = Schemas['LinePaymentIn']
export type MatchType = Schemas['MatchType']
export type RuleSource = Schemas['RuleSource']
export type InvoiceLine = Schemas['InvoiceLineOut']
export type InvoiceImport = Schemas['InvoiceImportOut']
export type InvoiceImportDetail = Schemas['InvoiceImportDetailOut']
export type InvoiceImportList = Schemas['InvoiceImportListOut']
export type LineUpdate = Schemas['LineUpdateIn']
export type CategoryRule = Schemas['RuleOut']
export type CategoryRuleInput = Schemas['RuleIn']

export type Flow = Schemas['FlowOut']
export type BudgetLine = Schemas['BudgetLineOut']
export type Thermometer = Schemas['ThermometerOut']
export type CategoryTotal = Schemas['CategoryTotalOut']
export type PendingOccurrence = Schemas['PendingOut']
export type MonthSummary = Schemas['MonthSummaryOut']
export type YearMonth = Schemas['YearMonthOut']
export type YearSummary = Schemas['YearSummaryOut']
export type PeriodTotals = Pick<MonthSummary, 'income' | 'needs' | 'wants' | 'savings' | 'balance_cents'>

/** Filtros que a tela de lançamentos usa (subconjunto dos parâmetros de GET /api/transactions). */
export interface TransactionFilters {
  month?: string
  kind?: Kind
  category_id?: number
  card_id?: number
  goal_id?: number
  q?: string
}
