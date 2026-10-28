import { describe, expect, it } from 'vitest'

import { centsToInput, formatCents, parseMoneyToCents } from './money'

describe('parseMoneyToCents', () => {
  it.each([
    ['1.234,56', 123456],
    ['1234,56', 123456],
    ['1234.56', 123456],
    ['12,5', 1250],
    ['0,99', 99],
    ['1.234', 123400], // ponto seguido de 3 dígitos é milhar, como se escreve no Brasil
    ['1.23', 123],
    ['1.234.567,00', 123456700],
    ['R$ 1.234,56', 123456],
    ['  100  ', 10000],
    ['0', 0],
  ])('converte %j em %d centavos', (input, expected) => {
    expect(parseMoneyToCents(input)).toBe(expected)
  })

  it.each(['', '   ', 'abc', '-5', '12,345', '1.2345', '1,2,3', ',50', '1e5', '10 reais', '9999999999999999999'])(
    'recusa %j',
    (input) => {
      expect(parseMoneyToCents(input)).toBeNull()
    },
  )
})

describe('formatCents', () => {
  it('formata em reais com separadores brasileiros', () => {
    expect(formatCents(123456).replace(/\s/g, ' ')).toBe('R$ 1.234,56')
    expect(formatCents(-5000).replace(/\s/g, ' ')).toBe('-R$ 50,00')
    expect(formatCents(0).replace(/\s/g, ' ')).toBe('R$ 0,00')
  })
})

describe('centsToInput', () => {
  it('gera o texto editável que o parser lê de volta', () => {
    expect(centsToInput(123456)).toBe('1.234,56')
    expect(parseMoneyToCents(centsToInput(123456))).toBe(123456)
    expect(centsToInput(5)).toBe('0,05')
  })
})
