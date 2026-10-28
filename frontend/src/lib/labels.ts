import type { Bucket, InvoiceStatus, Kind, PaymentMethod, ThermometerStatus } from './types'

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
  past: 'Encerrada',
}

export const THERMOMETER_LABELS: Record<ThermometerStatus, string> = {
  no_data: 'Sem dados',
  controlled: 'Controlado',
  warning: 'Atenção',
  negative: 'Negativo',
}
