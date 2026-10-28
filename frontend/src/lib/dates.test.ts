import { describe, expect, it } from 'vitest'

import {
  addMonths,
  currentMonth,
  formatDate,
  formatMonthInput,
  formatMonthLabel,
  formatMonthShort,
  monthOf,
  parseMonthInput,
  todayIso,
} from './dates'

describe('meses', () => {
  it('usa a data local, não UTC (às 23h30 no Brasil ainda é o mesmo dia)', () => {
    const lateNight = new Date(2026, 9, 31, 23, 30)
    expect(todayIso(lateNight)).toBe('2026-10-31')
    expect(currentMonth(lateNight)).toBe('2026-10')
  })

  it.each([
    ['2026-10', 1, '2026-11'],
    ['2026-12', 1, '2027-01'],
    ['2026-01', -1, '2025-12'],
    ['2026-03', -14, '2025-01'],
  ])('addMonths(%s, %d) = %s', (month, count, expected) => {
    expect(addMonths(month, count)).toBe(expected)
  })

  it('extrai o mês de uma data ISO', () => {
    expect(monthOf('2026-10-27')).toBe('2026-10')
  })
})

describe('formatação', () => {
  it('formata datas no padrão brasileiro sem deslocar o dia pelo fuso', () => {
    expect(formatDate('2026-10-01')).toBe('01/10/2026')
  })

  it('escreve o mês por extenso', () => {
    expect(formatMonthLabel('2026-03')).toBe('março de 2026')
  })

  it.each([
    ['07/2027', '2027-07'],
    ['7/2027', '2027-07'],
    [' 12/2026 ', '2026-12'],
    ['072027', '2027-07'], // teclado numérico do celular não tem barra
    ['2027-07', '2027-07'],
    ['13/2027', null],
    ['00/2027', null],
    ['07/27', null],
    ['07/1999', null],
    ['julho', null],
    ['', null],
  ])('parseMonthInput(%j) = %j', (typed, expected) => {
    expect(parseMonthInput(typed)).toBe(expected)
  })

  it('formatMonthInput mostra o mês como se escreve no Brasil', () => {
    expect(formatMonthInput('2027-07')).toBe('07/2027')
  })

  it('abrevia o mês sem ponto final, aceitando mês ou data', () => {
    expect(formatMonthShort('2026-10')).toBe('out/2026')
    expect(formatMonthShort('2027-06-30')).toBe('jun/2027')
  })
})
