import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, setUnauthorizedHandler } from './api'

function respond(status: number, body?: unknown) {
  const text = body === undefined ? '' : typeof body === 'string' ? body : JSON.stringify(body)
  return Promise.resolve(new Response(status === 204 ? null : text, { status }))
}

describe('api', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    setUnauthorizedHandler(null)
  })

  it('envia FormData sem Content-Type de JSON', async () => {
    fetchMock.mockReturnValue(respond(201, { id: 1, already_imported: false }))
    const form = new FormData()
    form.set('card_id', '3')
    await api.invoices.upload(form)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/invoice-imports')
    expect(init.method).toBe('POST')
    expect(init.body).toBe(form)
    expect(init.headers).not.toHaveProperty('Content-Type')
  })

  it('esquecer a senha da fatura chama a rota do cartão', async () => {
    fetchMock.mockReturnValue(respond(204))
    await api.cards.forgetInvoicePassword(4)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/cards/4/invoice-password')
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
  })

  it('envia JSON na mesma origem e devolve o corpo', async () => {
    fetchMock.mockReturnValue(respond(201, [{ id: 1 }]))
    const created = await api.transactions.create({
      description: 'Mercado',
      kind: 'expense',
      amount_cents: 1000,
      date: '2026-10-05',
      category_id: 3,
      payment_method: 'pix',
    })
    expect(created).toEqual([{ id: 1 }])
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/transactions')
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('same-origin')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toMatchObject({ description: 'Mercado', amount_cents: 1000 })
  })

  it('monta a query string só com filtros preenchidos', async () => {
    fetchMock.mockReturnValue(respond(200, []))
    await api.transactions.list({ month: '2026-10', q: 'uber', category_id: undefined })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/transactions?month=2026-10&q=uber')
  })

  it('transforma erros de validação em mensagens por campo', async () => {
    fetchMock.mockReturnValue(
      respond(422, {
        detail: 'Verifique os campos informados.',
        errors: [{ field: 'amount_cents', message: 'Informe um valor maior que 0.' }],
      }),
    )
    const error = await api.categories.list().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(422)
    expect((error as ApiError).message).toBe('Verifique os campos informados.')
    expect((error as ApiError).fieldErrors).toEqual({ amount_cents: 'Informe um valor maior que 0.' })
  })

  it('explica falha de rede em português', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const error = (await api.auth.me().catch((e: unknown) => e)) as ApiError
    expect(error.status).toBe(0)
    expect(error.message).toMatch(/servidor/)
  })

  it('não quebra quando o erro não é JSON (ex.: proxy fora do ar)', async () => {
    fetchMock.mockReturnValue(respond(502, '<html>Bad Gateway</html>'))
    const error = (await api.cards.list().catch((e: unknown) => e)) as ApiError
    expect(error.status).toBe(502)
    expect(error.message).toBe('O servidor respondeu com um erro (502). Tente de novo em instantes.')
  })

  it('só chama o tratamento de sessão quando a API diz que não há login válido', async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    fetchMock.mockReturnValue(respond(401, { detail: 'Usuário ou senha incorretos.', code: 'invalid_credentials' }))
    await api.auth.login('ana', 'errada').catch(() => undefined)
    fetchMock.mockReturnValue(
      respond(401, { detail: 'Usuário ou código inválido, ou o convite expirou.', code: 'invite_refused' }),
    )
    await api.auth.activate({ username: 'maria', code: 'AAAA-AAAA', password: 'senha-boa-123' }).catch(() => undefined)
    expect(onUnauthorized).not.toHaveBeenCalled()
    fetchMock.mockReturnValue(respond(401, { detail: 'Faça login para continuar.', code: 'session_expired' }))
    await api.goals.list().catch(() => undefined)
    fetchMock.mockReturnValue(respond(401, { detail: 'Faça login para continuar.', code: 'not_authenticated' }))
    await api.goals.list().catch(() => undefined)
    expect(onUnauthorized).toHaveBeenCalledTimes(2)
  })

  it('expõe o código do erro da API', async () => {
    fetchMock.mockReturnValue(
      respond(503, { detail: 'O banco de dados está indisponível agora.', code: 'database_unavailable' }),
    )
    const error = await api.goals.list().catch((failure: unknown) => failure)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('database_unavailable')
  })

  it('aceita respostas sem corpo (204)', async () => {
    fetchMock.mockReturnValue(respond(204))
    await expect(api.transactions.remove(5, 'installments')).resolves.toBeUndefined()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/transactions/5?scope=installments')
  })
})
