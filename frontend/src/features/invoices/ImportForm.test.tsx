import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '@/lib/api'
import type { Card } from '@/lib/types'

import { ImportForm } from './ImportForm'

vi.mock('@/lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/lib/api')>()
  return { ...original, api: { ...original.api, invoices: { ...original.api.invoices, upload: vi.fn() } } }
})

const upload = vi.mocked(api.invoices.upload)
const CARDS = [
  { id: 3, name: 'Inter', archived: false },
  { id: 4, name: 'Antigo', archived: true },
] as Card[]
const PDF = new File(['%PDF-1.7'], 'fatura.pdf', { type: 'application/pdf' })
const passwordError = (message: string) => new ApiError(422, 'Erro de validação', { password: message })
const imported = (id: number, alreadyImported = false) =>
  ({ id, already_imported: alreadyImported }) as Awaited<ReturnType<typeof api.invoices.upload>>

function renderForm() {
  render(
    <MemoryRouter initialEntries={['/faturas']}>
      <Routes>
        <Route path="/faturas" element={<ImportForm cards={CARDS} />} />
        <Route path="/faturas/:id" element={<p>Tela da fatura</p>} />
      </Routes>
    </MemoryRouter>,
  )
  return userEvent.setup()
}

async function chooseAndRead(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText('Cartão'), '3')
  await user.upload(screen.getByLabelText('Arquivo da fatura (PDF)'), PDF)
  await user.click(screen.getByRole('button', { name: 'Ler fatura' }))
}

function sentForm(call: number): FormData {
  return upload.mock.calls[call][0]
}

describe('ImportForm', () => {
  beforeEach(() => upload.mockReset())

  it('só oferece cartões ativos e exige cartão e arquivo', async () => {
    const user = renderForm()
    expect(screen.queryByRole('option', { name: 'Antigo' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Ler fatura' }))
    expect(screen.getByText('Escolha o cartão.')).toBeInTheDocument()
    expect(screen.getByText('Escolha o arquivo PDF da fatura.')).toBeInTheDocument()
    expect(upload).not.toHaveBeenCalled()
  })

  it('pede a senha quando a fatura tem senha e reenvia com ela', async () => {
    upload.mockRejectedValueOnce(passwordError('Esta fatura tem senha.')).mockResolvedValueOnce(imported(7))
    const user = renderForm()
    await chooseAndRead(user)
    expect(await screen.findByText('Esta fatura tem senha.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Senha da fatura'), '1234')
    await user.click(screen.getByLabelText('Salvar a senha no cartão Inter para as próximas faturas'))
    await user.click(screen.getByRole('button', { name: 'Abrir fatura' }))
    expect(await screen.findByText('Tela da fatura')).toBeInTheDocument()
    expect(sentForm(1).get('card_id')).toBe('3')
    expect(sentForm(1).get('file')).toBeInstanceOf(File)
    expect(sentForm(1).get('password')).toBe('1234')
    expect(sentForm(1).get('save_password')).toBe('true')
  })

  it('a senha não fica salva por padrão', async () => {
    upload.mockRejectedValueOnce(passwordError('Esta fatura tem senha.')).mockResolvedValueOnce(imported(7))
    const user = renderForm()
    await chooseAndRead(user)
    await user.type(await screen.findByLabelText('Senha da fatura'), '1234')
    await user.click(screen.getByRole('button', { name: 'Abrir fatura' }))
    await screen.findByText('Tela da fatura')
    expect(sentForm(1).get('save_password')).toBe('false')
  })

  it('mostra "Senha incorreta." e mantém o diálogo aberto', async () => {
    upload
      .mockRejectedValueOnce(passwordError('Esta fatura tem senha.'))
      .mockRejectedValueOnce(passwordError('Senha incorreta.'))
    const user = renderForm()
    await chooseAndRead(user)
    await user.type(await screen.findByLabelText('Senha da fatura'), 'errada')
    await user.click(screen.getByRole('button', { name: 'Abrir fatura' }))
    expect(await screen.findByText('Senha incorreta.')).toBeInTheDocument()
    expect(screen.getByLabelText('Senha da fatura')).toBeInTheDocument()
  })

  it('clique duplo em Ler fatura envia uma vez só', async () => {
    let finish: (value: ReturnType<typeof imported>) => void = () => {}
    upload.mockReturnValueOnce(new Promise((resolve) => (finish = resolve)))
    const user = renderForm()
    await user.selectOptions(screen.getByLabelText('Cartão'), '3')
    await user.upload(screen.getByLabelText('Arquivo da fatura (PDF)'), PDF)
    await user.dblClick(screen.getByRole('button', { name: 'Ler fatura' }))
    expect(screen.getByRole('button', { name: /Lendo/ })).toBeDisabled()
    finish(imported(9))
    await screen.findByText('Tela da fatura')
    expect(upload).toHaveBeenCalledTimes(1)
  })

  it('mostra o erro do arquivo vindo do servidor', async () => {
    upload.mockRejectedValueOnce(new ApiError(422, 'Erro', { file: 'Por enquanto só leio faturas do Inter.' }))
    const user = renderForm()
    await chooseAndRead(user)
    expect(await screen.findByText('Por enquanto só leio faturas do Inter.')).toBeInTheDocument()
  })
})
