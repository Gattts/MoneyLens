/**
 * Worker do Cloudflare: serve o frontend (arquivos estáticos de `dist/`) e repassa `/api/*` ao backend.
 *
 * Para o navegador, tela e API ficam na mesma origem. Por isso o cookie de sessão (SameSite=Strict)
 * funciona sem CORS e sem depender de cookies de terceiros, que o Safari bloqueia.
 */

export interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> }
  /** Endereço público do backend, ex.: https://financeiro-api.onrender.com */
  BACKEND_ORIGIN: string
  /** Segredo compartilhado com o backend (FIN_PROXY_SECRET): prova que o IP repassado é confiável. */
  PROXY_SECRET: string
}

// Cabeçalhos que só o Worker pode definir: os enviados por quem acessa são descartados.
const PROXY_HEADERS = ['x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-proxy-secret']
// Mesmos limites do backend (FIN_MAX_BODY_BYTES e FIN_MAX_UPLOAD_BYTES): corpo maior é recusado antes de ser lido.
const MAX_BODY_BYTES = 1024 * 1024
const UPLOAD_LIMITS: Record<string, number> = { '/api/invoice-imports': 5 * 1024 * 1024 }

function isApi(pathname: string) {
  return pathname === '/api' || pathname.startsWith('/api/')
}

async function proxyToBackend(request: Request, env: Env): Promise<Response> {
  if (!env.BACKEND_ORIGIN || !env.PROXY_SECRET) {
    return Response.json({ detail: 'A API não está configurada neste servidor.' }, { status: 503 })
  }
  const incoming = new URL(request.url)
  const maxBytes = UPLOAD_LIMITS[incoming.pathname] ?? MAX_BODY_BYTES
  if (Number(request.headers.get('content-length') ?? 0) > maxBytes) {
    return Response.json({ detail: 'Requisição grande demais.' }, { status: 413 })
  }
  const target = new URL(incoming.pathname + incoming.search, env.BACKEND_ORIGIN)

  const headers = new Headers(request.headers)
  headers.delete('host')
  for (const name of PROXY_HEADERS) headers.delete(name)
  const visitorIp = request.headers.get('cf-connecting-ip')
  if (visitorIp) headers.set('x-forwarded-for', visitorIp)
  headers.set('x-forwarded-host', incoming.host)
  headers.set('x-forwarded-proto', incoming.protocol.replace(':', ''))
  headers.set('x-proxy-secret', env.PROXY_SECRET)

  const hasBody = !['GET', 'HEAD'].includes(request.method)
  return fetch(
    new Request(target, {
      method: request.method,
      headers,
      // O tamanho já foi conferido acima; ler tudo aqui é simples e barato.
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: 'manual',
    }),
  )
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (isApi(new URL(request.url).pathname)) return proxyToBackend(request, env)
    return env.ASSETS.fetch(request)
  },
}
