import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '@/lib/api'

import { ImportActions } from './ImportActions'
import { SkippedSection } from './SkippedSection'
import { StandbySection } from './StandbySection'
import { category, detail, line } from './test-data'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...original,
    api: { ...original.api, invoiceLines: { update: vi.fn(), include: vi.fn(), ignore: vi.fn() } },
  }
})

const update = vi.mocked(api.invoiceLines.update)
const include = vi.mocked(api.invoiceLines.include)
const ignore = vi.mocked(api.invoiceLines.ignore)
const CATEGORIES = [category({ id: 10, name: 'Lazer' }), category({ id: 12, name: 'Salário', kind: 'income' })]
const PENDING = [
  line({ id: 1, merchant_key: 'LOJA NOVA', description: 'LOJA NOVA', amount_cents: 1000 }),
  line({ id: 2, merchant_key: 'LOJA NOVA', description: 'LOJA NOVA', amount_cents: 500 }),
]

describe('StandbySection', () => {
  beforeEach(() => {
    update.mockReset().mockResolvedValue(detail({}))
  })

  it('só oferece categorias de despesa e resolver com lembrar envia um PUT só', async () => {
    const user = userEvent.setup()
    const onChanged = vi.fn()
    render(<StandbySection lines={PENDING} categories={CATEGORIES} onChanged={onChanged} />)
    expect(screen.getByText('2×')).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Salário/ })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Categoria de LOJA NOVA'), '10')
    await user.click(screen.getByRole('button', { name: 'Resolver' }))
    expect(update).toHaveBeenCalledTimes(1)
    expect(update).toHaveBeenCalledWith(1, { category_id: 10, remember: true })
    expect(onChanged).toHaveBeenCalled()
  })

  it('resolver sem lembrar envia um PUT por linha', async () => {
    const user = userEvent.setup()
    render(<StandbySection lines={PENDING} categories={CATEGORIES} onChanged={vi.fn()} />)
    await user.selectOptions(screen.getByLabelText('Categoria de LOJA NOVA'), '10')
    await user.click(screen.getByLabelText('Lembrar LOJA NOVA nas próximas faturas'))
    await user.click(screen.getByRole('button', { name: 'Resolver' }))
    expect(update.mock.calls).toEqual([
      [1, { category_id: 10, remember: false }],
      [2, { category_id: 10, remember: false }],
    ])
  })

  it('pede a categoria antes de resolver', async () => {
    const user = userEvent.setup()
    render(<StandbySection lines={PENDING} categories={CATEGORIES} onChanged={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: 'Resolver' }))
    expect(screen.getByText('Escolha a categoria.')).toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })
})

describe('StandbySection no extrato', () => {
  const MARIA = [
    line({ id: 3, merchant_key: 'MARIA', description: 'MARIA', is_credit: true, amount_cents: 5000 }),
    line({ id: 4, merchant_key: 'MARIA', description: 'MARIA', amount_cents: 3000 }),
    line({ id: 5, merchant_key: 'MARIA', description: 'MARIA', amount_cents: 2000 }),
  ]

  it('entrada e saída do mesmo nome ficam em grupos separados, cada um com as categorias do seu tipo', () => {
    render(<StandbySection lines={MARIA} categories={CATEGORIES} onChanged={vi.fn()} />)
    const income = screen.getByLabelText('Categoria de MARIA (entrada)')
    const expense = screen.getByLabelText('Categoria de MARIA')
    expect(within(income).queryByRole('option', { name: /Salário/ })).toBeInTheDocument()
    expect(within(income).queryByRole('option', { name: /Lazer/ })).not.toBeInTheDocument()
    expect(within(expense).queryByRole('option', { name: /Lazer/ })).toBeInTheDocument()
    expect(within(expense).queryByRole('option', { name: /Salário/ })).not.toBeInTheDocument()
  })

  it('não lançar tira todas as linhas do grupo', async () => {
    ignore.mockReset().mockResolvedValue(detail({}))
    const user = userEvent.setup()
    const onChanged = vi.fn()
    render(<StandbySection lines={MARIA} categories={CATEGORIES} onChanged={onChanged} />)
    await user.click(screen.getByRole('button', { name: 'Não lançar MARIA' }))
    expect(ignore.mock.calls).toEqual([[4], [5]])
    expect(onChanged).toHaveBeenCalled()
  })
})

describe('SkippedSection', () => {
  it('possível duplicado oferece importar mesmo assim', async () => {
    include.mockReset().mockResolvedValue(detail({}))
    const user = userEvent.setup()
    const onChanged = vi.fn()
    const lines = [
      line({ id: 7, status: 'skipped', skip_reason: 'duplicate', description: 'UBER *TRIP' }),
      line({ id: 8, status: 'skipped', skip_reason: 'payment', description: 'PAGAMENTO ON LINE' }),
    ]
    render(<SkippedSection lines={lines} onChanged={onChanged} />)
    await user.click(screen.getByText('Fora da importação (2)'))
    expect(screen.getByText('Pagamento da fatura')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Importar mesmo assim' })).toHaveLength(1)
    await user.click(screen.getByRole('button', { name: 'Importar mesmo assim' }))
    expect(include).toHaveBeenCalledWith(7)
    expect(onChanged).toHaveBeenCalled()
  })
})

describe('SkippedSection no extrato', () => {
  it('traz de volta o que você não lançou, importa o que outro extrato já trouxe e aponta a fixa', async () => {
    include.mockReset().mockResolvedValue(detail({}))
    const user = userEvent.setup()
    const lines = [
      line({ id: 7, status: 'skipped', skip_reason: 'ignored', description: 'CARLOS' }),
      line({ id: 8, status: 'skipped', skip_reason: 'already_imported', description: 'PADARIA' }),
      line({ id: 9, status: 'skipped', skip_reason: 'duplicate', description: 'EMPRESA X', duplicate_of: 'Salário' }),
    ]
    render(<SkippedSection lines={lines} onChanged={vi.fn()} />)
    await user.click(screen.getByText('Fora da importação (3)'))
    expect(screen.getByText('Já importada em outro extrato')).toBeInTheDocument()
    expect(screen.getByText('Parece a fixa Salário: confirme a fixa no Painel.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Voltar para o standby' }))
    expect(include).toHaveBeenCalledWith(7)
    expect(screen.getAllByRole('button', { name: 'Importar mesmo assim' })).toHaveLength(2)
  })

  it('mostra o resumo do dinheiro guardado', async () => {
    const user = userEvent.setup()
    const lines = [line({ id: 1, status: 'skipped', skip_reason: 'investment', description: 'Aplicação RDB' })]
    render(
      <SkippedSection lines={lines} investment={{ applied_cents: 105000, redeemed_cents: 2700 }} onChanged={vi.fn()} />,
    )
    await user.click(screen.getByText('Fora da importação (1)'))
    expect(screen.getByText('Aplicou R$ 1.050,00, resgatou R$ 27,00.')).toBeInTheDocument()
  })
})

describe('ImportActions', () => {
  const identified = [line({ id: 1, status: 'identified', category_id: 10 })]

  it('antes de confirmar mostra Confirmar N e Descartar leitura', () => {
    render(
      <ImportActions invoice={detail({ lines: identified })} busy={false} onConfirm={vi.fn()} onDelete={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: 'Confirmar 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Descartar leitura' })).toBeInTheDocument()
  })

  it('depois de confirmar só mostra Desfazer importação', () => {
    const confirmed = detail({ confirmed_at: '2026-10-28T13:00:00Z', lines: identified })
    render(<ImportActions invoice={confirmed} busy={false} onConfirm={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.queryByRole('button', { name: /Confirmar/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Desfazer importação' })).toBeInTheDocument()
  })
})
