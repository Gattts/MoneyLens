import { PlusIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { FormDialog } from '@/components/FormDialog'
import { SectionCard } from '@/components/page'
import { LoadingBlock, QueryError } from '@/components/query-state'
import { RowActions } from '@/components/RowActions'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { MATCH_TYPE_LABELS, RULE_SOURCE_LABELS } from '@/lib/labels'
import { useCategories, useRefreshData, useRules } from '@/lib/queries'
import type { CategoryRule, CategoryRuleInput } from '@/lib/types'

import { RuleForm } from './RuleForm'

export function RulesSection() {
  const rules = useRules()
  const categories = useCategories()
  const refresh = useRefreshData()
  const [editing, setEditing] = useState<CategoryRule | 'new' | null>(null)
  const [removing, setRemoving] = useState<CategoryRule | null>(null)
  const [pending, setPending] = useState(false)

  async function save(body: CategoryRuleInput) {
    if (editing === 'new') await api.rules.create(body)
    else if (editing) await api.rules.update(editing.id, body)
    toast.success(editing === 'new' ? 'Regra criada.' : 'Regra atualizada.')
    setEditing(null)
    void refresh()
  }

  async function remove(rule: CategoryRule) {
    setPending(true)
    try {
      await api.rules.remove(rule.id)
      toast.success('Regra excluída.')
      setRemoving(null)
      void refresh()
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : 'Não foi possível excluir.')
    } finally {
      setPending(false)
    }
  }

  const categoryName = (id: number) => categories.data?.find((item) => item.id === id)?.name ?? '—'
  return (
    <SectionCard
      title="Regras"
      description="Como o app reconhece a categoria de cada compra. As suas valem antes das padrão."
      action={
        <Button size="sm" onClick={() => setEditing('new')}>
          <PlusIcon /> Nova regra
        </Button>
      }
    >
      {rules.isError ? (
        <QueryError error={rules.error} onRetry={() => void rules.refetch()} />
      ) : rules.isPending ? (
        <LoadingBlock rows={3} />
      ) : rules.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma regra ainda.</p>
      ) : (
        <ul className="flex flex-col divide-y">
          {rules.data.map((rule) => (
            <li key={rule.id} className="flex items-center justify-between gap-2 py-2 text-sm">
              <span className="min-w-0">
                <span className="block truncate font-mono">{rule.pattern}</span>
                <span className="text-muted-foreground">
                  {MATCH_TYPE_LABELS[rule.match_type]} → {categoryName(rule.category_id)}
                </span>
              </span>
              <span className="flex items-center gap-2">
                <Badge variant={rule.source === 'learned' ? 'default' : 'secondary'}>
                  {RULE_SOURCE_LABELS[rule.source]}
                </Badge>
                <RowActions
                  label={`regra ${rule.pattern}`}
                  onEdit={() => setEditing(rule)}
                  onDelete={() => setRemoving(rule)}
                />
              </span>
            </li>
          ))}
        </ul>
      )}
      <FormDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        title={editing === 'new' ? 'Nova regra' : 'Editar regra'}
      >
        <RuleForm
          initial={editing === 'new' || editing === null ? undefined : editing}
          categories={categories.data ?? []}
          onSubmit={save}
          onCancel={() => setEditing(null)}
        />
      </FormDialog>
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => !open && setRemoving(null)}
        pending={pending}
        title="Excluir regra?"
        description="Lançamentos já importados não mudam."
        actions={[{ label: 'Excluir', destructive: true, onConfirm: () => removing && void remove(removing) }]}
      />
    </SectionCard>
  )
}
