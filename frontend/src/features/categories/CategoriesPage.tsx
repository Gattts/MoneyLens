import { ArchiveIcon, ArchiveRestoreIcon, PlusIcon } from 'lucide-react'
import { toast } from 'sonner'

import { PageHeader, SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormDialog } from '@/components/FormDialog'
import { RowActions } from '@/components/RowActions'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useEditor, useQuickAction, useRemove } from '@/hooks/useCrud'
import { api } from '@/lib/api'
import { BUCKET_LABELS } from '@/lib/labels'
import { useCategories, useRefreshData } from '@/lib/queries'
import type { Category, CategoryInput, Kind } from '@/lib/types'
import { cn } from '@/lib/utils'

import { CategoryForm } from './CategoryForm'

function toInput(category: Category): CategoryInput {
  const { id, ...input } = category
  return input
}

interface CategoryTableProps {
  categories: Category[]
  kind: Kind
  onEdit: (category: Category) => void
  onArchive: (category: Category) => void
  onRemove: (category: Category) => void
  archiving: boolean
}

function CategoryTable({ categories, kind, onEdit, onArchive, onRemove, archiving }: CategoryTableProps) {
  const rows = categories.filter((category) => category.kind === kind)
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">Nenhuma categoria.</p>
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Categoria</TableHead>
          {kind === 'expense' && <TableHead>Grupo</TableHead>}
          <TableHead className="hidden md:table-cell">O que entra aqui</TableHead>
          <TableHead className="w-28">
            <span className="sr-only">Ações</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((category) => (
          <TableRow key={category.id} className={cn(category.archived && 'text-muted-foreground')}>
            <TableCell className="font-medium">
              {`${category.icon} ${category.name}`.trim()}
              {category.archived && (
                <Badge variant="secondary" className="ml-2">
                  Arquivada
                </Badge>
              )}
            </TableCell>
            {kind === 'expense' && (
              <TableCell>{category.default_bucket ? BUCKET_LABELS[category.default_bucket] : '—'}</TableCell>
            )}
            <TableCell className="hidden max-w-md whitespace-normal text-muted-foreground md:table-cell">
              {category.description}
            </TableCell>
            <TableCell>
              <RowActions label={category.name} onEdit={() => onEdit(category)} onDelete={() => onRemove(category)}>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  disabled={archiving}
                  aria-label={`${category.archived ? 'Desarquivar' : 'Arquivar'} ${category.name}`}
                  onClick={() => onArchive(category)}
                >
                  {category.archived ? <ArchiveRestoreIcon /> : <ArchiveIcon />}
                </Button>
              </RowActions>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function CategoriesPage() {
  const categories = useCategories()
  const refresh = useRefreshData()
  const editor = useEditor<Category>()
  const removal = useRemove<Category>(api.categories.remove, 'Categoria excluída.')
  const archive = useQuickAction(
    (category: Category) => api.categories.update(category.id, { ...toInput(category), archived: !category.archived }),
    (category) => (category.archived ? `“${category.name}” voltou para a lista.` : `“${category.name}” arquivada.`),
  )

  async function save(body: CategoryInput) {
    if (editor.item) await api.categories.update(editor.item.id, body)
    else await api.categories.create(body)
    toast.success(editor.item ? 'Categoria atualizada.' : 'Categoria criada.')
    void refresh()
    editor.setOpen(false)
  }

  const tableProps = {
    onEdit: editor.edit,
    onArchive: archive.mutate,
    onRemove: removal.ask,
    archiving: archive.isPending,
  }
  return (
    <>
      <PageHeader
        title="Categorias"
        description="Cada categoria de despesa já sugere o grupo do orçamento (necessidade, desejo ou poupança)."
        actions={
          <Button onClick={editor.create}>
            <PlusIcon /> Nova categoria
          </Button>
        }
      />
      {categories.isError ? (
        <QueryError error={categories.error} onRetry={() => void categories.refetch()} />
      ) : categories.isPending ? (
        <LoadingBlock rows={6} />
      ) : (
        <div className="flex flex-col gap-4">
          <SectionCard title="Despesas">
            <CategoryTable categories={categories.data} kind="expense" {...tableProps} />
          </SectionCard>
          <SectionCard title="Receitas">
            <CategoryTable categories={categories.data} kind="income" {...tableProps} />
          </SectionCard>
        </div>
      )}

      <FormDialog
        open={editor.open}
        onOpenChange={editor.setOpen}
        title={editor.item ? 'Editar categoria' : 'Nova categoria'}
      >
        <CategoryForm
          key={editor.item?.id ?? 'nova'}
          initial={editor.item}
          onSubmit={save}
          onCancel={() => editor.setOpen(false)}
        />
      </FormDialog>

      <ConfirmDialog
        open={removal.target !== null}
        onOpenChange={(open) => !open && removal.dismiss()}
        title={`Excluir a categoria “${removal.target?.name ?? ''}”?`}
        description="Só é possível excluir uma categoria sem lançamentos. Se ela já tiver histórico, arquive-a."
        pending={removal.pending}
        actions={[{ label: 'Excluir', destructive: true, onConfirm: removal.confirm }]}
      />
    </>
  )
}
