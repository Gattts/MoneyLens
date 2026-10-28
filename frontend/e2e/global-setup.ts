import { execFileSync } from 'node:child_process'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { INVOICE_PASSWORD, INVOICE_PDF } from './helpers'

/** Gera a fatura sintética do E2E com o mesmo gerador dos testes do backend. */
export default function globalSetup() {
  const backend = fileURLToPath(new URL('../../backend', import.meta.url))
  const env = {
    ...process.env,
    PATH: `${path.join(os.homedir(), '.local', 'bin')}${path.delimiter}${process.env.PATH}`,
  }
  execFileSync(
    'uv',
    ['run', '--directory', backend, 'python', '-m', 'tests.invoice_samples', INVOICE_PDF, INVOICE_PASSWORD],
    { env, stdio: 'inherit' },
  )
}
