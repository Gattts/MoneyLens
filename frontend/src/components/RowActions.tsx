import { PencilIcon, Trash2Icon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'

interface RowActionsProps {
  /** Nome do item, usado no rótulo acessível ("Editar Aluguel"). */
  label: string
  onEdit: () => void
  onDelete: () => void
  /** Ações extras entre Editar e Excluir, como arquivar. */
  children?: ReactNode
}

/** Botões de ação de uma linha de tabela. */
export function RowActions({ label, onEdit, onDelete, children }: RowActionsProps) {
  return (
    <div className="flex justify-end">
      <Button variant="ghost" size="icon-sm" aria-label={`Editar ${label}`} onClick={onEdit}>
        <PencilIcon />
      </Button>
      {children}
      <Button variant="ghost" size="icon-sm" aria-label={`Excluir ${label}`} onClick={onDelete}>
        <Trash2Icon />
      </Button>
    </div>
  )
}
