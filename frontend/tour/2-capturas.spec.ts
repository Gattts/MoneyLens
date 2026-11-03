import path from 'node:path'

import { test } from '@playwright/test'

import { login, navigate } from '../e2e/helpers'
import { OUTPUT } from './seed'

// Os dados já foram criados pelo 1-tour.spec.ts, no mesmo servidor.
test.use({ viewport: { width: 1440, height: 900 }, video: 'off' })

const PAGES = [
  ['painel', 'Painel'],
  ['lancamentos', 'Lançamentos'],
  ['cartoes', 'Cartões'],
  ['importar', 'Importar'],
  ['previsao', 'Previsão'],
  ['tetos', 'Tetos'],
] as const

for (const scheme of ['light', 'dark'] as const) {
  test(`capturas no tema ${scheme === 'light' ? 'claro' : 'escuro'}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme })
    await login(page)
    for (const [file, label] of PAGES) {
      await navigate(page, label)
      // Na importação, a revisão da fatura diz mais que o formulário de envio.
      if (file === 'importar') await page.locator('a[href^="/faturas/"]').first().click()
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(400) // animações curtas de entrada
      await page.screenshot({ path: path.join(OUTPUT, 'screens', scheme, `${file}.png`) })
    }
  })
}
