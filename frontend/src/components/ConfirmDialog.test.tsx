import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ConfirmDialog } from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('clique duplo na ação chama a ação uma vez só', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn(() => new Promise<void>(() => {}))
    render(
      <ConfirmDialog
        open
        onOpenChange={vi.fn()}
        title="Excluir?"
        description="Não dá para desfazer."
        actions={[{ label: 'Excluir', destructive: true, onConfirm }]}
      />,
    )
    await user.dblClick(screen.getByRole('button', { name: 'Excluir' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Excluir/ })).toBeDisabled()
  })
})
