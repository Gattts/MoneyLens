import type {
  MatchType,
  RuleSource,
  SkipReason,
  Bucket,
  InvoiceStatus,
  PaymentSource,
  Kind,
  PaymentMethod,
  ThermometerStatus,
  UserStatus,
} from './types'

export const KIND_LABELS: Record<Kind, string> = { expense: 'Despesa', income: 'Receita' }

export const BUCKET_LABELS: Record<Bucket, string> = {
  needs: 'Necessidades',
  wants: 'Desejos',
  savings: 'Poupança',
}

export const BUCKET_HINTS: Record<Bucket, string> = {
  needs: 'Contas essenciais: moradia, mercado, saúde, transporte.',
  wants: 'O que é bom ter, mas dá para cortar: lazer, delivery, compras.',
  savings: 'Dinheiro guardado ou investido, inclusive aportes em metas.',
}

export const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  pix: 'Pix',
  debit: 'Débito',
  cash: 'Dinheiro',
  bank_slip: 'Boleto',
  transfer: 'Transferência',
  credit_card: 'Cartão de crédito',
}

export const PAYMENT_METHODS = Object.keys(PAYMENT_LABELS) as PaymentMethod[]
export const BUCKETS = Object.keys(BUCKET_LABELS) as Bucket[]

export const INVOICE_STATUS_LABELS: Record<InvoiceStatus, string> = {
  future: 'Futura',
  open: 'Aberta',
  closed: 'Fechada',
  paid: 'Paga',
  partially_paid: 'Paga em parte',
  overdue: 'Vencida, sem pagamento',
  paid_before_tracking: 'Paga (antes do registro)',
}

export const PAYMENT_SOURCE_LABELS: Record<PaymentSource, string> = {
  manual: 'à mão',
  card_invoice: 'da fatura seguinte',
  account_statement: 'do extrato',
}

export const THERMOMETER_LABELS: Record<ThermometerStatus, string> = {
  no_data: 'Sem dados',
  controlled: 'Controlado',
  warning: 'Atenção',
  negative: 'Negativo',
}

export const SKIP_REASON_LABELS: Record<SkipReason, string> = {
  payment: 'Pagamento da fatura',
  refund: 'Estorno (a compra foi anulada)',
  credit: 'Crédito sem compra correspondente (lance à mão se quiser)',
  duplicate: 'Possível duplicado de um lançamento seu',
  existing_installment: 'Parcela já lançada',
  card_payment: 'Pagamento de fatura',
  own_transfer: 'Transferência entre suas contas',
  investment: 'Investimento (veja o resumo do RDB)',
  already_imported: 'Já importada em outro extrato',
  ignored: 'Você escolheu não lançar',
}

const BANK_NAMES: Record<string, string> = { inter: 'Inter', nubank: 'Nubank' }

export const bankName = (code: string) => BANK_NAMES[code] ?? code

export const MATCH_TYPE_LABELS: Record<MatchType, string> = { exact: 'Exata', contains: 'Contém' }

export const RULE_SOURCE_LABELS: Record<RuleSource, string> = { default: 'Padrão', learned: 'Sua' }

export const USER_STATUS_LABELS: Record<UserStatus, string> = {
  active: 'Ativo',
  pending: 'Aguardando primeiro acesso',
  expired: 'Convite expirado',
}
