import fs from 'node:fs'
import path from 'node:path'

import { type APIRequestContext, type APIResponse, expect } from '@playwright/test'

import { INVOICE_PASSWORD, INVOICE_PDF } from '../e2e/helpers'

/** Saída do tour (ignorada pelo git), copiada depois para o portfólio. */
export const OUTPUT = path.resolve('tour-output')

// Tudo aqui é inventado: nomes genéricos, valores fixos e um gerador determinístico (a mesma semente dá o mesmo tour).
const CLOSED_MONTHS = 4
const SALARY = 650_000
const FIXED = [
  { description: 'Aluguel', category: 'Moradia', amount_cents: 180_000, day_of_month: 10, payment_method: 'bank_slip' },
  { description: 'Internet', category: 'Moradia', amount_cents: 11_990, day_of_month: 15, payment_method: 'debit' },
  { description: 'Streaming', category: 'Assinaturas', amount_cents: 4_590, day_of_month: 20, payment_method: 'debit' },
] as const
const VARIABLE = [
  {
    description: 'Mercado Central',
    category: 'Mercado',
    days: [3, 10, 17, 24],
    min: 22_000,
    max: 34_000,
    method: 'debit',
  },
  {
    description: 'Padaria do Bairro',
    category: 'Comida fora',
    days: [6, 13, 20, 27],
    min: 4_500,
    max: 9_000,
    method: 'pix',
  },
  {
    description: 'App de transporte',
    category: 'Transporte',
    days: [2, 9, 16, 23],
    min: 1_800,
    max: 4_200,
    method: 'card',
  },
  { description: 'Cinema', category: 'Lazer', days: [12, 26], min: 6_000, max: 15_000, method: 'pix' },
  { description: 'Farmácia Saúde', category: 'Farmácia e higiene', days: [8], min: 3_000, max: 9_000, method: 'debit' },
] as const
// No mês atual, a comida fora fica perto do teto de R$ 300 (para mostrar o alerta).
const THIS_MONTH_FOOD = [9_500, 8_700, 8_900]

let state = 42
function between(min: number, max: number): number {
  state = (state * 1_103_515_245 + 12_345) % 2 ** 31
  return min + (state % (max - min + 1))
}

const pad = (value: number) => String(value).padStart(2, '0')

async function ok<T>(response: Promise<APIResponse>): Promise<T> {
  const done = await response
  expect(done.ok(), `${done.url()} → ${done.status()} ${await done.text()}`).toBe(true)
  return (await done.json()) as T
}

export async function seedDemo(request: APIRequestContext, today: Date): Promise<void> {
  state = 42
  const firstOfMonth = (offset: number) => new Date(today.getFullYear(), today.getMonth() + offset, 1)
  const monthOf = (offset: number) => {
    const first = firstOfMonth(offset)
    return `${first.getFullYear()}-${pad(first.getMonth() + 1)}`
  }
  // Mês atual: só dias até hoje, para nada ficar no futuro.
  const dateOf = (offset: number, day: number) =>
    `${monthOf(offset)}-${pad(offset === 0 ? Math.min(day, today.getDate()) : day)}`

  const categories = await ok<Array<{ id: number; name: string }>>(request.get('/api/categories'))
  const category = (name: string) => {
    const found = categories.find((item) => item.name === name)
    if (!found) throw new Error(`categoria padrão ausente: ${name}`)
    return found.id
  }
  const card = await ok<{ id: number }>(
    request.post('/api/cards', {
      data: { name: 'Cartão Principal', limit_cents: 800_000, closing_day: 3, due_day: 10 },
    }),
  )
  const spare = await ok<{ id: number }>(
    request.post('/api/cards', {
      data: { name: 'Cartão Reserva', limit_cents: 300_000, closing_day: 20, due_day: 28 },
    }),
  )

  const recurring = [
    {
      description: 'Salário',
      kind: 'income',
      amount_cents: SALARY,
      category: 'Salário',
      day_of_month: 5,
      payment_method: 'transfer',
    },
    ...FIXED.map((item) => ({ ...item, kind: 'expense' })),
  ]
  for (const item of recurring) {
    const { category: name, ...body } = item
    const rule = await ok<{ id: number }>(
      request.post('/api/recurring', {
        data: { ...body, category_id: category(name), start_month: monthOf(-CLOSED_MONTHS) },
      }),
    )
    for (let offset = -CLOSED_MONTHS; offset < 0; offset++) {
      await ok(request.post(`/api/recurring/${rule.id}/confirm`, { data: { month: monthOf(offset) } }))
    }
  }

  for (let offset = -CLOSED_MONTHS; offset <= 0; offset++) {
    for (const item of VARIABLE) {
      if (offset === 0 && item.category === 'Comida fora') continue
      for (const day of item.days) {
        if (offset === 0 && day > today.getDate()) continue
        const onCard = item.method === 'card'
        await ok(
          request.post('/api/transactions', {
            data: {
              description: item.description,
              kind: 'expense',
              amount_cents: between(item.min, item.max),
              date: dateOf(offset, day),
              category_id: category(item.category),
              payment_method: onCard ? 'credit_card' : item.method,
              ...(onCard ? { card_id: card.id } : {}),
            },
          }),
        )
      }
    }
  }
  for (const [index, amount] of THIS_MONTH_FOOD.entries()) {
    await ok(
      request.post('/api/transactions', {
        data: {
          description: 'Restaurante da Praça',
          kind: 'expense',
          amount_cents: amount,
          date: dateOf(0, 1 + index * 3),
          category_id: category('Comida fora'),
          payment_method: 'pix',
        },
      }),
    )
  }
  await ok(
    request.post('/api/transactions', {
      data: {
        description: 'Notebook',
        kind: 'expense',
        amount_cents: 360_000,
        date: dateOf(-2, 12),
        category_id: category('Eletrônicos'),
        payment_method: 'credit_card',
        card_id: card.id,
        installments: 6,
      },
    }),
  )

  // Uma fatura sintética (a mesma do E2E) fica na tela de importação, esperando revisão.
  await ok(
    request.post('/api/invoice-imports', {
      multipart: {
        source: 'card_invoice',
        card_id: String(spare.id),
        password: INVOICE_PASSWORD,
        file: { name: 'fatura.pdf', mimeType: 'application/pdf', buffer: fs.readFileSync(INVOICE_PDF) },
      },
    }),
  )

  await ok(request.post('/api/limits', { data: { category_id: category('Comida fora'), amount_cents: 30_000 } }))
  await ok(request.post('/api/limits', { data: { category_id: category('Lazer'), income_percent: 5 } }))
}
