import { defineConfig, devices } from '@playwright/test'

import { PASSWORD as E2E_PASSWORD, USERNAME as E2E_USERNAME } from '../e2e/helpers'

// Tour para o portfólio: sobe o app com um banco SQLite temporário (o mesmo do E2E), cria dados inventados, grava o
// vídeo e tira as capturas. Roda com `npm run tour`; não faz parte do E2E normal.
const TIMEZONE = 'America/Sao_Paulo'
process.env.TZ = TIMEZONE
const port = 8767

export default defineConfig({
  testDir: '.',
  testMatch: /\d-.*\.spec\.ts$/,
  globalSetup: '../e2e/global-setup.ts',
  outputDir: '../tour-results',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 240_000,
  reporter: [['list']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: `http://127.0.0.1:${port}`,
    locale: 'pt-BR',
    timezoneId: TIMEZONE,
  },
  webServer: {
    command: 'npm run build && bash e2e/run-server.sh',
    cwd: '..',
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: { E2E_PORT: String(port), E2E_USERNAME, E2E_PASSWORD },
  },
})
