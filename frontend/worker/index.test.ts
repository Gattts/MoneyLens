// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'

import worker, { type Env } from './index'

const assets = { fetch: vi.fn(async () => new Response('<html>app</html>')) }
const env: Env = { ASSETS: assets, BACKEND_ORIGIN: 'https://api.exemplo.com', PROXY_SECRET: 'segredo-compartilhado' }

afterEach(() => {
  vi.unstubAllGlobals()
  assets.fetch.mockClear()
})

function stubBackend(response = new Response('{"ok":true}', { status: 201 })) {
  const backend = vi.fn(async (_request: Request) => response)
  vi.stubGlobal('fetch', backend)
  return backend
}

describe('Worker do Cloudflare', () => {
  it('repassa /api ao backend com caminho, método, corpo e cookie', async () => {
    const backend = stubBackend()
    const request = new Request('https://financeiro.exemplo.com/api/transactions?month=2026-10', {
      method: 'POST',
      headers: { cookie: 'fin_session=abc', 'content-type': 'application/json', 'cf-connecting-ip': '203.0.113.7' },
      body: '{"description":"Feira"}',
    })
    const response = await worker.fetch(request, env)
    const sent = backend.mock.calls[0][0]
    expect(sent.url).toBe('https://api.exemplo.com/api/transactions?month=2026-10')
    expect(sent.method).toBe('POST')
    expect(await sent.text()).toBe('{"description":"Feira"}')
    expect(sent.headers.get('cookie')).toBe('fin_session=abc')
    expect(sent.headers.get('x-forwarded-for')).toBe('203.0.113.7')
    expect(sent.headers.get('x-proxy-secret')).toBe('segredo-compartilhado')
    expect(response.status).toBe(201)
  })

  it('descarta cabeçalhos de proxy forjados por quem acessa', async () => {
    const backend = stubBackend()
    const forged = new Request('https://financeiro.exemplo.com/api/auth/login', {
      method: 'POST',
      headers: { 'x-forwarded-for': '1.2.3.4', 'x-proxy-secret': 'chute', 'cf-connecting-ip': '198.51.100.9' },
      body: '{}',
    })
    await worker.fetch(forged, env)
    const sent = backend.mock.calls[0][0]
    expect(sent.headers.get('x-forwarded-for')).toBe('198.51.100.9')
    expect(sent.headers.get('x-proxy-secret')).toBe('segredo-compartilhado')
  })

  it('devolve a resposta do backend como veio, inclusive o cookie de sessão', async () => {
    stubBackend(new Response(null, { status: 204, headers: { 'set-cookie': 'fin_session=novo; HttpOnly; Secure' } }))
    const response = await worker.fetch(
      new Request('https://financeiro.exemplo.com/api/auth/logout', { method: 'POST' }),
      env,
    )
    expect(response.status).toBe(204)
    expect(response.headers.get('set-cookie')).toContain('fin_session=novo')
  })

  it('o resto é servido pelos arquivos estáticos', async () => {
    const backend = stubBackend()
    await worker.fetch(new Request('https://financeiro.exemplo.com/lancamentos'), env)
    expect(assets.fetch).toHaveBeenCalledOnce()
    expect(backend).not.toHaveBeenCalled()
  })

  it('sem configuração, recusa em vez de chamar o backend sem o segredo', async () => {
    const backend = stubBackend()
    const response = await worker.fetch(new Request('https://financeiro.exemplo.com/api/health'), {
      ...env,
      PROXY_SECRET: '',
    })
    expect(response.status).toBe(503)
    expect(backend).not.toHaveBeenCalled()
  })

  it('recusa corpo grande demais antes de ler e de chamar o backend', async () => {
    const backend = stubBackend()
    const huge = new Request('https://financeiro.exemplo.com/api/auth/login', {
      method: 'POST',
      headers: { 'content-length': String(2 * 1024 * 1024) },
      body: 'x',
    })
    const response = await worker.fetch(huge, env)
    expect(response.status).toBe(413)
    expect(backend).not.toHaveBeenCalled()
  })
})
