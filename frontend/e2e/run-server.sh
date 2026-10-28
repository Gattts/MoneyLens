#!/usr/bin/env bash
# Sobe o backend com um banco temporário para os testes de ponta a ponta.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
FIN_DATA_DIR="$(mktemp -d)"
# Definido aqui para valer mais que o backend/.env, que pode apontar para o banco de verdade (Supabase):
# os testes trocariam o usuário e a senha e gravariam lançamentos de teste nele.
FIN_DATABASE_URL="sqlite:///$FIN_DATA_DIR/e2e.db"
export FIN_DATA_DIR FIN_DATABASE_URL
trap 'rm -rf "$FIN_DATA_DIR"' EXIT
cd "$(dirname "$0")/../../backend"
printf '%s\n%s\n' "$E2E_PASSWORD" "$E2E_PASSWORD" | uv run financeiro set-password --username "$E2E_USERNAME" > /dev/null 2>&1
uv run financeiro serve --port "$E2E_PORT"
