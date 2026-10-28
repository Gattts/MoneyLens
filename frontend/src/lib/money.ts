/** Valores trafegam em centavos inteiros: nunca usamos float para dinheiro. */

export const MAX_AMOUNT_CENTS = 100_000_000_000 // R$ 1 bilhão, mesmo limite da API

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const plain = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// "1.234,56" ou "1234,56": vírgula decimal, pontos opcionais de milhar.
const COMMA_DECIMAL = /^(\d{1,3}(\.\d{3})*|\d+)(,\d{1,2})?$/
// "1.234" ou "1.234.567": só milhar (como se escreve no Brasil).
const DOT_THOUSANDS = /^\d{1,3}(\.\d{3})+$/
// "1234.56" ou "12.5": ponto decimal (teclado numérico de alguns celulares).
const DOT_DECIMAL = /^\d+(\.\d{1,2})?$/

/** Converte o que a pessoa digitou em centavos. Devolve null se não for um valor válido. */
export function parseMoneyToCents(raw: string): number | null {
  const text = raw.replace(/R\$/i, '').replace(/\s/g, '')
  let normalized: string
  if (text.includes(',')) {
    if (!COMMA_DECIMAL.test(text)) return null
    normalized = text.replace(/\./g, '').replace(',', '.')
  } else if (DOT_THOUSANDS.test(text)) {
    normalized = text.replace(/\./g, '')
  } else if (DOT_DECIMAL.test(text)) {
    normalized = text
  } else {
    return null
  }
  const [whole, fraction = ''] = normalized.split('.')
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
  return Number.isSafeInteger(cents) ? cents : null
}

export function formatCents(cents: number): string {
  return currency.format(cents / 100)
}

/** Texto para preencher um campo de valor ao editar ("1.234,56"). */
export function centsToInput(cents: number): string {
  return plain.format(cents / 100)
}
