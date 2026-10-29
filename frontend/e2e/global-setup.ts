import { execFileSync } from 'node:child_process'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { INVOICE_PASSWORD, INVOICE_PDF, STATEMENT_PDF } from './helpers'

/** Gera a fatura e o extrato sintéticos do E2E com os mesmos geradores dos testes do backend. */
export default function globalSetup() {
  const backend = fileURLToPath(new URL('../../backend', import.meta.url))
  const env = {
    ...process.env,
    PATH: `${path.join(os.homedir(), '.local', 'bin')}${path.delimiter}${process.env.PATH}`,
  }
  const run = (...args: string[]) =>
    execFileSync('uv', ['run', '--directory', backend, 'python', '-m', ...args], { env, stdio: 'inherit' })
  run('tests.invoice_samples', INVOICE_PDF, INVOICE_PASSWORD)
  run('tests.statement_samples', STATEMENT_PDF)
}
