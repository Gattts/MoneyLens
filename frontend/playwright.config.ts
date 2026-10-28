import { defineConfig, devices } from '@playwright/test'

import { PASSWORD as E2E_PASSWORD, USERNAME as E2E_USERNAME } from './e2e/helpers'

const port = Number(process.env.E2E_PORT ?? 8766)
// Com E2E_BASE_URL, os testes rodam contra um servidor já no ar (ex.: `wrangler dev` na frente do backend).
const externalUrl = process.env.E2E_BASE_URL

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: externalUrl ?? `http://127.0.0.1:${port}`,
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] }, testIgnore: /mobile\.spec\.ts/ },
    { name: 'celular', use: { ...devices['Pixel 7'] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: externalUrl
    ? undefined
    : {
        command: 'npm run build && bash e2e/run-server.sh',
        url: `http://127.0.0.1:${port}/api/health`,
        reuseExistingServer: false,
        timeout: 120_000,
        env: { E2E_PORT: String(port), E2E_USERNAME, E2E_PASSWORD },
      },
})
