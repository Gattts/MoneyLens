/**
 * Datas trafegam como texto ISO ("2026-10-27") e meses como "2026-10".
 * Nada aqui usa toISOString(): ele converte para UTC e, no Brasil, muda o dia depois das 21h.
 */

const pad = (value: number) => String(value).padStart(2, '0')

const monthLabel = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' })

export function todayIso(now = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

export function currentMonth(now = new Date()): string {
  return monthOf(todayIso(now))
}

export function monthOf(iso: string): string {
  return iso.slice(0, 7)
}

export function addMonths(month: string, count: number): string {
  const [year, monthNumber] = month.split('-').map(Number)
  const index = year * 12 + (monthNumber - 1) + count
  return `${Math.floor(index / 12)}-${pad((index % 12) + 1)}`
}

export function formatDate(iso: string): string {
  const [year, month, day] = iso.split('-')
  return `${day}/${month}/${year}`
}

export function formatMonthLabel(month: string): string {
  const [year, monthNumber] = month.split('-').map(Number)
  return monthLabel.format(new Date(Date.UTC(year, monthNumber - 1, 1)))
}

const MONTH_ABBREVIATIONS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/** "out/2026" a partir de "2026-10" ou "2026-10-27". */
export function formatMonthShort(value: string): string {
  const [year, monthNumber] = value.split('-').map(Number)
  return `${MONTH_ABBREVIATIONS[monthNumber - 1]}/${year}`
}

// "07/2027", "7/2027" ou só dígitos "072027" (o teclado numérico do celular não tem barra).
const MONTH_TYPED_BR = /^(\d{1,2})\/?(\d{4})$/
const MONTH_TYPED_ISO = /^(\d{4})-(\d{2})$/

/** Mês digitado ("07/2027", "072027" ou "2027-07") → "2027-07". Fora de 2000–2100 ou inválido → null. */
export function parseMonthInput(text: string): string | null {
  const value = text.trim()
  const br = MONTH_TYPED_BR.exec(value)
  const iso = MONTH_TYPED_ISO.exec(value)
  const year = Number(br ? br[2] : iso?.[1])
  const month = Number(br ? br[1] : iso?.[2])
  if (!(month >= 1 && month <= 12 && year >= 2000 && year <= 2100)) return null
  return `${year}-${pad(month)}`
}

/** "2027-07" → "07/2027", o jeito de escrever que o campo de mês aceita. */
export function formatMonthInput(month: string): string {
  const [year, monthNumber] = month.split('-')
  return `${monthNumber}/${year}`
}
