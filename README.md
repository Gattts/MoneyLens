# Financeiro

Ferramenta web de finanças pessoais que substitui a planilha "Controle de Gastos". Ela mantém o que a planilha
fazia bem (orçamento 50/30/20, termômetro, despesas fixas previstas, cartões, metas, balanço anual) e corrige o
que fazia mal: datas em texto, uma aba copiada por mês, fatura sem ciclo de fechamento, parcelas em texto livre e
lançamentos que sumiam dos totais. O porquê de cada decisão está em
[docs/analise-planilha.md](docs/analise-planilha.md).

- **Backend:** Python 3.12, [uv](https://docs.astral.sh/uv/), FastAPI, SQLAlchemy e Alembic, sobre **PostgreSQL**
  (em produção, no [Supabase](https://supabase.com/)). Sem configuração, usa SQLite local para começar rápido.
- **Frontend:** React, TypeScript, Vite, Tailwind e shadcn/ui, publicado no **Cloudflare** (Workers).

```
navegador ──► Cloudflare Worker ──┬─► arquivos do React (dist/)
             (mesma origem)       └─► /api/* ──► backend (container) ──► PostgreSQL (Supabase)
```

## Pré-requisitos

- `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh` (ele baixa o Python certo sozinho).
- Node.js 22 ou mais novo, com npm.
- Opcional: Docker, para rodar o Postgres local (`compose.yaml`) e gerar a imagem do backend.

## Desenvolvimento

```bash
# 1. Backend
cd backend
uv sync                               # instala as dependências
uv run financeiro set-password        # cria o usuário (pede a senha duas vezes, mínimo 8 caracteres)
uv run financeiro serve --reload      # API em http://127.0.0.1:8000

# 2. Frontend (outro terminal)
cd frontend
npm install
npm run dev                           # abra http://localhost:5173
```

O Vite repassa `/api` para o backend, então tela e API ficam na mesma origem e o login funciona sem
configuração extra.

Sem `FIN_DATABASE_URL`, o backend usa um SQLite em `backend/data/`. Para desenvolver no mesmo banco da
produção, suba o Postgres local e aponte para ele:

```bash
docker compose up -d
echo 'FIN_DATABASE_URL=postgresql://financeiro:financeiro-local@127.0.0.1:5432/financeiro' >> backend/.env
```

## Testes e qualidade

| Onde | Comando | O que verifica |
|---|---|---|
| backend | `uv run pytest` | regras de negócio, API, segurança, migrações e CLI (no SQLite) |
| backend | `FIN_TEST_DATABASE_URL=postgresql://… uv run pytest` | a mesma suíte num Postgres, mais migrações e RLS |
| backend | `uv run ruff check src tests && uv run ruff format --check src tests` | lint e formatação |
| backend | `uv run mypy src` | tipos (modo estrito) |
| frontend | `npm test` | utilitários, formulários e o Worker do Cloudflare (Vitest) |
| frontend | `npm run lint && npm run typecheck && npm run format:check` | ESLint, TypeScript e Prettier |
| frontend | `npm run e2e` | fluxos completos num navegador de verdade (Playwright) |

O `npm run e2e` gera o build, sobe o backend com um banco temporário e roda os testes no desktop e no celular.
Antes da primeira vez, rode `npx playwright install chromium`. A CI (`.github/workflows/ci.yml`) roda tudo isso
a cada push.

## Banco de dados no Supabase

1. Crie um projeto no Supabase na região mais próxima do backend. O Render não tem região na América do Sul;
   este projeto usa `us-west-2`, a mesma do Render `oregon` (o `render.yaml` já usa `oregon`).
2. Em **Connect**, copie a URI do **Session pooler**. A conexão direta (`db.<ref>.supabase.co`) só tem
   IPv6 e **não funciona no Render**. O pooler funciona em qualquer rede. O formato é
   `postgresql://postgres.<ref>:<SENHA>@aws-<n>-<região>.pooler.supabase.com:5432/postgres`. Se a senha tiver
   caracteres especiais, codifique-os (`@` vira `%40`).
3. Coloque a URI em `FIN_DATABASE_URL` (no `backend/.env` ou nas variáveis do servidor). O backend troca o
   driver para o psycopg e liga `sslmode=require` sozinho.
4. Crie as tabelas e o usuário:
   ```bash
   cd backend
   uv run financeiro migrate        # tabelas, categorias padrão e proteção do Supabase
   uv run financeiro set-password
   ```
5. **Recomendado:** em *Project Settings → Data API*, desligue a Data API, porque a ferramenta não a usa. Mesmo
   ligada, as migrações ativam RLS sem políticas e revogam o acesso dos papéis `anon` e `authenticated`, então a
   chave pública do projeto não lê nem altera nada.

Para verificar também o certificado do servidor (`require` cifra, mas não confere quem responde), baixe o
certificado em *Project Settings → Database → SSL* e acrescente à URI
`?sslmode=verify-full&sslrootcert=/caminho/prod-ca-2021.crt`.

Observações: no plano gratuito, o projeto pausa depois de uma semana sem uso, e o backup diário automático
existe só nos planos pagos. Para backup próprio, use `pg_dump "$FIN_DATABASE_URL" > backup.sql`.

## Publicação: frontend no Cloudflare, backend em container

### 1. Backend

A pasta `backend/` tem um `Dockerfile` que funciona em qualquer plataforma de containers (Render, Fly.io,
Railway, Cloud Run, uma VPS…). A plataforma precisa entregar HTTPS. Configure estas variáveis:

| Variável | Valor |
|---|---|
| `FIN_DATABASE_URL` | URI do Supabase (passo anterior) |
| `FIN_SECRET_KEY` | segredo aleatório (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `FIN_PROXY_SECRET` | **outro** segredo aleatório; o mesmo valor vai para o Worker |
| `FIN_ALLOWED_HOSTS` | o domínio do backend na plataforma, ex.: `financeiro-api.onrender.com` |
| `FIN_PROXY_ONLY` | `true`: a API só atende quem chega pelo Worker (acesso direto ao backend recebe 403; `/api/health` fica livre) |

A imagem já sobe com `FIN_COOKIE_SECURE=true`, usa a porta da variável `PORT` e aplica as migrações ao
iniciar. O health check fica em `/api/health`. Se a plataforma checar a saúde com outro nome de host, inclua
esse nome em `FIN_ALLOWED_HOSTS`.

```bash
docker build -t financeiro-api backend      # para testar a imagem localmente
```

#### Render

O [render.yaml](render.yaml) descreve o serviço (Docker, plano gratuito, região `oregon`, health check e
variáveis). No Render, não é preciso definir `FIN_ALLOWED_HOSTS`, porque o endereço `xxx.onrender.com` é
aceito sozinho (o Render informa esse endereço em `RENDER_EXTERNAL_HOSTNAME`).

1. Suba o repositório para o GitHub.
2. No painel do Render: **New → Blueprint** e escolha o repositório.
3. O Render pede dois valores. Em `FIN_DATABASE_URL`, cole a URI do **Session pooler**. Em
   `FIN_PROXY_SECRET`, cole um segredo novo e guarde-o para o Worker. O `FIN_SECRET_KEY` é gerado sozinho.
4. Depois do primeiro deploy, anote o endereço do serviço (ex.: `https://financeiro-api.onrender.com`) e
   confira que `/api/health` responde `{"status":"ok"}`.

No plano gratuito, o serviço dorme depois de 15 minutos sem acesso, e o primeiro acesso depois disso demora
cerca de um minuto.

### 2. Frontend (Cloudflare Workers)

O Worker serve o build do React e repassa `/api/*` ao backend. Para o navegador, tudo fica na mesma origem:
o cookie de sessão funciona sem CORS e sem cookie de terceiros. O Worker também envia ao backend o IP real de
quem acessa, assinado com o `PROXY_SECRET`, para o limite de tentativas de login valer por pessoa.

```bash
cd frontend
npx wrangler login
# em wrangler.jsonc, troque BACKEND_ORIGIN pelo endereço HTTPS do backend
npx wrangler secret put PROXY_SECRET        # cole o mesmo valor de FIN_PROXY_SECRET
npm run cloudflare:deploy                   # build + publicação
```

Para publicar a cada push em vez de pela linha de comando, conecte o repositório em *Workers & Pages →
Create → Import a repository*, com *Root directory* `frontend`, *Build command* `npm run build` e *Deploy
command* `npx wrangler deploy`. O `PROXY_SECRET` continua sendo configurado com `wrangler secret put` ou no
painel, em *Settings → Variables and Secrets*.

Para usar um domínio próprio, vá ao painel do Cloudflare, em *Workers → financeiro → Settings → Domains &
Routes*. Os cabeçalhos de segurança dos arquivos estáticos (CSP, HSTS…) ficam em `frontend/public/_headers`.

Para testar a pilha inteira antes de publicar, com o backend rodando em `127.0.0.1:8000` e `FIN_PROXY_SECRET`
definido, crie `frontend/.dev.vars` com `PROXY_SECRET=<o mesmo valor>` e rode `npm run cloudflare:dev`. A suíte
de ponta a ponta roda através dele com `E2E_BASE_URL=http://127.0.0.1:8787 npm run e2e`.

### Sem Cloudflare (uma máquina só)

O backend também serve o build do React. Gere o build com `npm run build`, rode `uv run financeiro serve` e
coloque na frente um proxy reverso com HTTPS (Caddy, por exemplo), usando `FIN_COOKIE_SECURE=true` e
`FIN_ALLOWED_HOSTS` com o seu domínio.

## Leitor de faturas

Na página **Faturas**, escolha o cartão e o PDF da fatura (por enquanto, só do Inter) e clique em **Ler fatura**.

- **Senha do PDF:** se a fatura tiver senha, um pop-up pede a senha. Ela é usada só naquela leitura, a menos que
  você marque "Salvar a senha no cartão". Nesse caso, ela fica cifrada no banco com uma chave derivada do
  `FIN_SECRET_KEY` e nunca volta pela API. Para apagá-la, use **Esquecer senha** na página Cartões. O PDF nunca é
  gravado: ele é lido em memória e descartado.
- **Conferência:** a soma das compras lidas precisa bater com o total que o banco imprime para cada cartão. Se não
  bater, nada é importado.
- **Reconhecimento:** primeiro valem as suas regras exatas e depois as palavras-chave do dicionário inicial (ex.:
  UBER → Transporte). O que não for reconhecido fica **em standby**. Ao resolver um gasto com "lembrar", o app
  aprende a regra e resolve na hora os iguais, inclusive em outras faturas. As regras ficam editáveis na mesma
  página.
- **Ficam fora da importação:**
  - pagamentos da fatura;
  - estornos, junto com a compra que eles anulam;
  - créditos sem compra correspondente;
  - parcelas que já existem;
  - possíveis duplicados de lançamentos feitos à mão (mesmo cartão e valor, data até 3 dias de diferença), que
    têm a opção "importar mesmo assim".
- **Confirmar:** cria os lançamentos. Numa compra parcelada, cria também as parcelas futuras. **Desfazer
  importação** apaga tudo o que a fatura criou.
- **Limites:** até 5 MiB e 30 páginas por arquivo. A mesma fatura (mesmo cartão e vencimento) não entra duas vezes.

Guarde faturas reais só na pasta `referencia/`, que fica fora do git. Os testes usam faturas sintéticas, geradas
por `backend/tests/invoice_samples.py`.

## Configuração

Todas as variáveis são opcionais e podem ficar em `backend/.env`. Há um modelo comentado em
[backend/.env.example](backend/.env.example).

| Variável | Padrão | Para que serve |
|---|---|---|
| `FIN_DATA_DIR` | `backend/data` | Pasta do banco e da chave de sessão (criada com permissão 700) |
| `FIN_DATABASE_URL` | SQLite em `FIN_DATA_DIR` | PostgreSQL (Supabase ou local), no formato que o Supabase entrega |
| `FIN_SECRET_KEY` | gerada em `FIN_DATA_DIR/secret_key` | Chave que assina o cookie de sessão (mínimo 32 caracteres) |
| `FIN_PROXY_SECRET` | — | Segredo compartilhado com o Worker do Cloudflare (mínimo 32 caracteres) |
| `FIN_PROXY_ONLY` | `false` | Recusa requisições à API que não venham pelo Worker (exige `FIN_PROXY_SECRET`) |
| `FIN_COOKIE_SECURE` | `false` (`true` na imagem Docker) | `true` quando o acesso for por HTTPS |
| `FIN_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Nomes de host aceitos (barra DNS rebinding). No Render, `RENDER_EXTERNAL_HOSTNAME` entra sozinho |
| `FIN_SESSION_MAX_AGE_SECONDS` | `604800` (7 dias) | Duração da sessão |
| `FIN_LOGIN_MAX_ATTEMPTS` / `FIN_LOGIN_WINDOW_SECONDS` | `5` / `900` | Tentativas de login antes do bloqueio temporário |
| `FIN_MAX_BODY_BYTES` | `1048576` | Tamanho máximo de uma requisição |
| `FIN_MAX_UPLOAD_BYTES` | `5242880` | Tamanho máximo do PDF da fatura (só no envio de faturas) |
| `FIN_ENABLE_DOCS` | `false` | Documentação interativa da API em `/api/docs` (só em desenvolvimento) |
| `FIN_FRONTEND_DIST` | `frontend/dist` | Pasta do build do frontend servido pelo backend |

## Dados, backup e senha

- No Supabase, faça backup com `pg_dump` (veja acima). No SQLite local, o banco fica em
  `backend/data/financeiro.db` com permissão 600; copie-o com
  `sqlite3 backend/data/financeiro.db ".backup 'financeiro-backup.db'"`.
- **Trocar a senha:** `uv run financeiro set-password`. Todas as sessões abertas são encerradas.
- **Sair** no menu também encerra a sessão em todos os aparelhos.
- Não versione `backend/data/`, `backend/.env`, `frontend/.dev.vars` nem `referencia/` (que guarda a planilha
  com dados reais). O `.gitignore` já exclui todos.

## Estrutura

```
backend/
  src/financeiro/
    domain/       regras puras: meses, ciclo do cartão, parcelas, fixas, orçamento, metas
    services/     operações com banco reaproveitadas pelas rotas (resumos, faturas, validações)
    routers/      rotas da API, uma por recurso
    schemas/      formatos de entrada e saída (Pydantic)
    migrations/   migrações Alembic (a primeira já cadastra as categorias padrão)
    app.py        montagem da aplicação, middlewares de segurança e servidor da SPA
    cli.py        comandos serve, migrate, set-password e openapi
  tests/          (test_postgres.py roda só com FIN_TEST_DATABASE_URL)
  Dockerfile      imagem do backend para produção
frontend/
  src/
    features/     uma pasta por tela (painel, lançamentos, fixas, cartões, metas…)
    components/   componentes compartilhados (ui/ = gerados pelo shadcn)
    lib/          cliente da API, tipos, dinheiro, datas, validação
  worker/         Worker do Cloudflare: serve o build e repassa /api ao backend
  e2e/            testes de ponta a ponta (Playwright)
  wrangler.jsonc  configuração do Cloudflare
docs/             análise da planilha, design e relatórios da banca de revisão
compose.yaml      Postgres 17 local para desenvolvimento
render.yaml       blueprint do backend no Render
```

## Documentação

- [Análise da planilha](docs/analise-planilha.md): o que mantivemos e o que reformulamos.
- [Design](docs/superpowers/specs/2026-10-27-ferramenta-financeira-design.md): modelo de dados, regras e API.
- Banca de revisão: [rodada 1](docs/revisao/rodada-1.md) · [rodada 2](docs/revisao/rodada-2.md).
