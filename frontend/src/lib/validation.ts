import { z } from 'zod'

import { MAX_AMOUNT_CENTS, parseMoneyToCents } from './money'

export const MIN_DATE = '2000-01-01'
export const MAX_DATE = '2100-12-31'

/** Campo de valor em reais digitado como texto ("1.234,56"). */
export function moneyField({ emptyMessage = 'Informe o valor.', allowZero = false } = {}) {
  return z.string().superRefine((value, ctx) => {
    if (!value.trim()) {
      ctx.addIssue({ code: 'custom', message: emptyMessage })
      return
    }
    const cents = parseMoneyToCents(value)
    if (cents === null) ctx.addIssue({ code: 'custom', message: 'Valor inválido. Exemplo: 1.234,56' })
    else if (cents < 0 || (cents === 0 && !allowZero))
      ctx.addIssue({ code: 'custom', message: 'Informe um valor maior que zero.' })
    else if (cents > MAX_AMOUNT_CENTS)
      ctx.addIssue({ code: 'custom', message: 'O valor máximo é R$ 1.000.000.000,00.' })
  })
}

function isRealDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
}

/** Data ISO obrigatória dentro do intervalo aceito pela API. */
export function dateField(emptyMessage = 'Informe a data completa (dia, mês e ano).') {
  return z.string().superRefine((value, ctx) => {
    if (!value) ctx.addIssue({ code: 'custom', message: emptyMessage })
    else if (!isRealDate(value)) ctx.addIssue({ code: 'custom', message: 'Data inválida.' })
    else if (value < MIN_DATE || value > MAX_DATE)
      ctx.addIssue({ code: 'custom', message: 'Use uma data entre 01/01/2000 e 31/12/2100.' })
  })
}

/** Inteiro digitado num campo de texto/número, dentro de [min, max]. */
export function integerText(min: number, max: number, message: string) {
  return z.string().refine((value) => /^\d+$/.test(value.trim()) && +value >= min && +value <= max, message)
}

/** Mês "AAAA-MM" (o campo type="month" vira texto em navegadores sem suporte). */
export function isMonthText(value: string): boolean {
  const match = /^(\d{4})-(\d{2})$/.exec(value)
  return Boolean(match) && +match![2] >= 1 && +match![2] <= 12 && +match![1] >= 2000 && +match![1] <= 2100
}
