# MoneyLens

O pacote Python, o comando de linha (`financeiro`) e o nome do Worker no Cloudflare continuam `financeiro`; só a
marca que aparece para quem usa passou a ser MoneyLens.

Ferramenta web de finanças pessoais que substitui a planilha "Controle de Gastos". Ela mantém o que a planilha
fazia bem (orçamento 50/30/20, termômetro, despesas fixas previstas, cartões, metas, balanço anual) e corrige o
que fazia mal: datas em texto, uma aba copiada por mês, fatura sem ciclo de fechamento, parcelas em texto livre e
lançamentos que sumiam dos totais. O estudo de caso em [jpaulos.dev](https://jpaulos.dev) resume as decisões de
produto e de arquitetura.

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

### Capturas para o portfólio

`npm run tour` (no `frontend/`) refaz as imagens e o vídeo do MoneyLens que aparecem no portfólio. Ele sobe o app
com o mesmo banco temporário do E2E e cria uma conta de demonstração **só com dados inventados**
(`frontend/tour/seed.ts`): 4 meses de histórico, dois cartões, uma compra parcelada, fixas, uma fatura sintética
e dois tetos. O banco é sempre um SQLite novo, criado só para o tour (nunca o do `backend/.env`); antes de semear,
o tour ainda confere que entrou com o usuário de teste e que o mês atual está vazio. Depois percorre as telas e grava em `frontend/tour-output/` (fora do git):

- `screens/{light,dark}/*.png`: Painel, Lançamentos, Cartões, Importar, Previsão e Tetos, em 1440×900;
- `tour.mp4` (H.264, 1280×720) e `poster.jpg`;
- `chapters.json`: o momento de cada parada, com o texto em português e em inglês (vira as legendas do vídeo).

A conversão para MP4 usa o `ffmpeg` instalado (`sudo apt install ffmpeg`) ou, sem ele, a imagem Docker
`jrottenberg/ffmpeg:7.1-alpine`. O mês atual só recebe lançamentos até o dia de hoje: rodando a partir do dia 15,
as telas saem mais cheias. Rode de novo sempre que o visual do app mudar e copie a pasta para o portfólio.

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

**Endereço:** o app fica em **`https://moneylens.jpaulos.dev`**, declarado em `routes` no `wrangler.jsonc`
(`custom_domain: true`). Como o domínio `jpaulos.dev` está na mesma conta do Cloudflare, o `npm run
cloudflare:deploy` cria o registro de DNS e o certificado sozinho. O endereço antigo (`financeiro.<conta>.workers.dev`)
continua ativo enquanto `workers_dev` for `true`; quando ninguém mais usar, troque para `false` e publique de novo. O
login é guardado por endereço, então quem usa entra de novo no endereço novo. Para trocar de domínio, mude a rota
(ou use o painel, em *Workers → financeiro → Settings → Domains & Routes*). Os cabeçalhos de segurança dos arquivos
estáticos (CSP, HSTS…) ficam em `frontend/public/_headers`.

Para testar a pilha inteira antes de publicar, com o backend rodando em `127.0.0.1:8000` e `FIN_PROXY_SECRET`
definido, crie `frontend/.dev.vars` com `PROXY_SECRET=<o mesmo valor>` e rode `npm run cloudflare:dev`. A suíte
de ponta a ponta roda através dele com `E2E_BASE_URL=http://127.0.0.1:8787 npm run e2e`.

### Sem Cloudflare (uma máquina só)

O backend também serve o build do React. Gere o build com `npm run build`, rode `uv run financeiro serve` e
coloque na frente um proxy reverso com HTTPS (Caddy, por exemplo), usando `FIN_COOKIE_SECURE=true` e
`FIN_ALLOWED_HOSTS` com o seu domínio.

## Usuários e primeiro acesso

Cada pessoa tem os próprios dados (lançamentos, cartões, categorias, regras e faturas) e não vê os dos outros.

- **Primeiro administrador:** `uv run financeiro set-password` num banco vazio cria o primeiro usuário, já como
  administrador e com o pacote padrão (24 categorias, palavras-chave das faturas e orçamento 50/30/20). Num banco que
  já tinha dados, a migração `0004` passa tudo para o usuário existente, que vira administrador.
- **Convidar alguém:** na página **Usuários** (só para administradores), cadastre o nome e envie à pessoa o texto com
  o código de convite. O código aparece uma única vez, vale 7 dias e é de uso único.
- **Primeiro acesso:** na tela de login, a pessoa clica em **Primeiro acesso**, informa o usuário e o código e escolhe a
  senha (de 8 a 128 caracteres).
- **Esqueceu a senha:** o administrador gera um novo convite. A senha antiga deixa de funcionar e as sessões abertas
  da pessoa caem.
- **Nomes de usuário:** de 3 a 50 caracteres, com letras, números, ponto, hífen ou sublinhado, sem espaços. Variações
  só de maiúsculas ou acentos contam como o mesmo nome ("João.Silva" e "joao.silva"), tanto no cadastro quanto no
  login.
- **Isolamento:** um teste percorre todas as rotas da API como outro usuário e falha se surgir uma rota nova sem regra
  de isolamento (`backend/tests/test_isolation.py`).

## Leitor de faturas

Na página **Importar**, escolha **Fatura do cartão**, o cartão e o PDF da fatura (por enquanto, só do Inter) e
clique em **Ler fatura**.

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

## Extrato da conta

Na mesma página **Importar**, escolha **Extrato da conta** e o PDF do extrato (por enquanto, só do Nubank). O
extrato não usa cartão. A revisão é a mesma da fatura: identificados, standby e o que ficou fora.

- **Conferência:** a soma das linhas precisa bater com o total de cada bloco do dia, com o total de entradas e de
  saídas e com o saldo final (saldo inicial + entradas − saídas). Se algo não bater, nada é importado.
- **Entradas e saídas:** o que saiu vira despesa e o que entrou vira receita, com a forma de pagamento da linha
  (Pix, débito ou transferência). As regras têm tipo: uma entrada só casa com regra de categoria de receita.
  Assim, um Pix enviado e um recebido da mesma pessoa podem ter categorias diferentes.
- **Ficam fora da importação:**
  - pagamento da fatura do cartão (os gastos já vêm pela fatura);
  - transferências entre contas do próprio titular;
  - linhas que outro extrato do mesmo banco já trouxe (mesma data, valor, sentido e nome), para que extratos com
    períodos sobrepostos não lancem nada duas vezes;
  - aplicações e resgates, um a um;
  - possíveis duplicados de um lançamento feito à mão (fora do cartão) ou de uma fixa ainda não confirmada, com
    a opção "importar mesmo assim".
- **Dinheiro guardado:** aplicações menos resgates do período viram **uma** linha "Dinheiro guardado no período",
  que a regra padrão leva para Investimentos. Se o saldo for negativo, nada entra.
- **Não lançar:** tira uma linha da importação (um Pix entre amigos, por exemplo). Ela fica na seção "fora" e pode
  voltar para o standby.
- **Repetido:** o mesmo extrato (mesmo banco e período) não entra duas vezes.

Os testes usam extratos sintéticos, gerados por `backend/tests/statement_samples.py`.

## Pagamento das faturas

Pagar a fatura **não cria lançamento**: as compras no cartão já são as despesas. O app só registra que a fatura foi
quitada, para mostrar a situação real e calcular o limite usado.

- **Situação:** "Paga em DD/MM", "Paga em parte (faltam R$ X)", "Vencida, sem pagamento", "Fechada", "Aberta",
  "Futura" ou "Paga (antes do registro)".
- **Marco:** cada cartão registra pagamentos a partir de uma data (a da migração, nos cartões que já existiam; a do
  cadastro, nos novos). Faturas que venceram antes disso contam como pagas.
- **Limite usado:** fatura aberta e parcelas futuras, mais o que falta pagar das faturas fechadas desde o marco. Uma
  fatura vencida sem pagamento continua ocupando o limite.
- **Três formas de registrar:**
  - **à mão:** em Cartões → Ver faturas → "Marcar como paga" (data e valor; valor menor registra pagamento em parte);
  - **pela fatura seguinte:** ao importar a fatura do Inter, o crédito "PAGAMENTO" registra o pagamento da fatura
    anterior (desfazer a importação apaga o registro);
  - **pelo extrato:** o "Pagamento de fatura" ou um Pix com o valor exato do que falta numa fatura perto do
    vencimento fica fora da importação como sugestão; "Registrar pagamento" confirma e "Não é pagamento" devolve a
    linha ao fluxo normal.

## Previsão do mês

A página **Previsão** mostra, no mês atual, quanto você deve gastar até o fim do mês em cada categoria: um **valor
provável** (metade das vezes o mês fecha abaixo dele) e um **máximo provável** (o mês não deve passar dele em 9 de cada
10 vezes). Ao lado vem a **estatística**, uma conta sem IA: gasto até hoje + fixas com data depois de hoje + média
diária do gasto variável dos meses anteriores × dias que faltam. Uma categoria ganha o selo **"Acima do normal"**
quando o gasto já passou do máximo provável, ou vai passar no ritmo do mês (a partir do dia 7 e com gasto de pelo menos
R$ 50). O Painel mostra só um resumo (provável, gasto e máximo provável) e, com menos de 3 meses fechados de histórico,
diz "Dados insuficientes para prever".

- **Modelo:** uma rede neural pequena, em PyTorch, com perda quantílica (prevê a mediana e o quantil de 90%). Ela
  recebe medidas do seu histórico: gasto até hoje, fixas a vir, média e último mês da categoria, quanto do mês já
  passou, fins de semana restantes e meses de histórico.
- **Modelo base:** treinado só com dados sintéticos (`financeiro treinar-base`), fica no repositório
  (`backend/src/financeiro/forecast/base.onnx`). É o que vale para quem ainda não tem modelo próprio.
- **Modelo próprio:** cada usuário ganha o seu, ajustado a partir do base só com os dados dele, a partir de 2 meses
  fechados. O treino roda fora do servidor, na sua máquina:

  ```bash
  cd backend
  uv sync --group ml          # PyTorch (só CPU) e ONNX, só para treinar; a produção não instala
  uv run financeiro treinar   # ou: uv run financeiro treinar --username ana
  ```

  O comando lê o banco configurado, valida cada modelo no último mês fechado, grava a versão nova no banco e
  imprime só métricas: erro médio do modelo, erro da estatística no mesmo teste e cobertura do máximo provável (o ideal é
  perto de 90%). Ele nunca imprime lançamentos.
- **No app:** o modelo roda com `onnxruntime`, sem PyTorch. O modelo de cada pessoa fica no banco (tabela
  `forecast_models`, com RLS) e nunca vai para o repositório. A estatística aparece ao lado, como referência.

### Rotina de treino

Uma vez por mês, entre os dias 1 e 5, na sua máquina:

```bash
cd backend
uv sync --group ml          # só na primeira vez ou depois de atualizar as dependências
uv run financeiro treinar   # todos os usuários; ou --username ana para um só
```

- **Por que no começo do mês:** o treino só usa meses fechados. Rodar de novo no mesmo mês não ensina nada e só cria
  uma versão repetida. A exceção é depois de importar muitos extratos antigos de uma vez.
- **Banco:** o comando lê o banco do `backend/.env` (o de produção). Ele não migra nada: sem a tabela
  `forecast_models`, avisa e para. Publique a versão nova (com as migrações) antes de treinar.
- **Quem ganha modelo:** cada usuário com pelo menos 2 meses fechados ganha uma versão nova; quem tem menos continua
  no modelo base, e usuário novo usa o base sem fazer nada. O app usa sempre a versão mais recente de cada pessoa.
- **Privacidade:** o treino carrega em memória os dados de todos os usuários treinados e imprime só métricas. Para
  treinar só o seu modelo, use `--username`.
- **Agendar na sua máquina** (`crontab -e`), por exemplo todo dia 2 às 9h:

  ```cron
  0 9 2 * * cd $HOME/acompanhamento-financeiro/backend && uv run financeiro treinar >> $HOME/financeiro-treino.log 2>&1
  ```

### Manutenção da previsão

- **Atualizar o PyTorch:** `uv lock --upgrade-package torch`, depois
  `uv sync --group ml && uv run pytest tests/test_forecast_training.py`. O CI não instala o grupo `ml`, então esses
  testes só rodam na sua máquina; rode-os antes do commit. O `test_onnx_export_matches_pytorch` confere que o modelo
  exportado dá o mesmo resultado no `onnxruntime` do servidor.
- **Atualizar o `onnxruntime`** (o lado do servidor): rode a suíte completa. Se um modelo antigo deixar de carregar, o
  app usa o modelo base daquela pessoa até o próximo treino, e o log avisa "Modelo de previsão ilegível".
- **Mudar as medidas** (`forecast/features.py`): suba `FEATURE_VERSION`, gere o modelo base de novo
  (`uv run financeiro treinar-base`) e faça commit de `base.onnx` e `base.pt`. Depois da publicação, todos usam o base
  até você rodar `treinar` de novo.
- **Voltar a uma versão anterior:** não há comando. Apague a versão nova no editor SQL do Supabase
  (`DELETE FROM forecast_models WHERE user_id = <id> AND version = <versão>;`) e o app volta a usar a anterior.
- **Se algo der errado no servidor:** sem modelo legível, a previsão usa o base; sem previsão nenhuma, os tetos de
  gasto continuam avisando 50/90/100% (só o "vai estourar" fica de fora).

## Tetos de gasto

Na página **Tetos**, cada categoria de despesa pode ter um teto mensal, de duas formas:

- **Valor fixo:** "Comida fora: R$ 300".
- **Porcentagem da renda:** "Lazer: 10% da renda". A conta usa a renda prevista do mês, a mesma do card Orçamento
  (receitas lançadas mais as fixas de receita ainda a confirmar). O valor em reais muda a cada mês e também no meio do
  mês, se entrar uma renda extra; os alertas comparam com o valor atual. Num mês sem renda prevista, o teto por
  porcentagem fica inativo ("Sem renda neste mês").

O teto vale todo mês até você mudar. A sugestão do app é só um ponto de partida: você define o valor ou a
porcentagem.

- **Alertas:** o app avisa quando o gasto do mês (do dia 1 até hoje) chega a **50%**, **90%** e **100%** do teto, e
  também **antes de estourar**, quando a previsão do mês indica que vai passar ("deve passar do teto"). Esse último
  só aparece a partir do dia 7.
- **Um aviso por vez:** cada marco avisa uma vez por mês por teto e volta a valer no mês seguinte. Se um gasto pula
  vários marcos, aparece só o mais grave (100% > vai estourar > 90% > 50%); os outros ficam registrados em silêncio.
- **Mudar o valor ou a forma** (R$ ou %) recomeça os alertas do mês do teto. **Teto inativo:** o de uma categoria
  arquivada não gera alerta e volta a valer se ela for desarquivada.
- **Sugestão:** ao escolher a categoria, o app sugere um valor (o provável do mês pela previsão, ou a média dos
  últimos meses, arredondado para cima de R$ 10 em R$ 10) e mostra quanto você costuma gastar. No modo porcentagem,
  a sugestão vem em % da renda prevista, arredondada para cima. Categoria sem histórico: você informa o valor, e a
  sugestão vem depois do primeiro mês.
- **Onde aparecem:** no sino (menu lateral no computador, cabeçalho no celular), num aviso no topo do Painel, no card
  "Tetos do mês" e num aviso rápido: ao entrar no app (uma vez por sessão) e quando surge um alerta novo, como logo
  depois de um lançamento.
- **Quando o app confere:** depois de lançar, editar ou excluir, confirmar uma fixa, confirmar ou desfazer uma
  importação, e ao abrir o Painel ou o sino (para pegar a virada do dia). Se a previsão estiver indisponível, os
  marcos de percentual continuam valendo.

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
docs/             (local, fora do git) análises, specs e planos de cada entrega
compose.yaml      Postgres 17 local para desenvolvimento
render.yaml       blueprint do backend no Render
```

## Documentação

As análises, specs e planos de cada entrega ficam em `docs/`, fora do repositório, porque partem de dados reais de
uso (a planilha e extratos). Este README cobre como usar, publicar e manter o app; o estudo de caso em
[jpaulos.dev](https://jpaulos.dev) conta o porquê das principais decisões.
