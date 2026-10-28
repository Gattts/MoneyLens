import { useState } from 'react'
import { toast } from 'sonner'

import { SectionCard } from '@/components/page'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { formatDate } from '@/lib/dates'
import { formatCents } from '@/lib/money'
import type { Category, InvoiceLine } from '@/lib/types'

import { CategorySelect } from './CategorySelect'
import { groupIdentified } from './invoice-groups'

export function IdentifiedSection({
  lines,
  categories,
  onChanged,
}: {
  lines: InvoiceLine[]
  categories: Category[]
  onChanged: () => void
}) {
  const [remember, setRemember] = useState(true)
  const groups = groupIdentified(lines, categories)

  async function change(line: InvoiceLine, categoryId: number | null) {
    if (categoryId === null || categoryId === line.category_id) return
    try {
      await api.invoiceLines.update(line.id, { category_id: categoryId, remember })
      onChanged()
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : 'Não foi possível trocar a categoria.')
    }
  }

  return (
    <SectionCard
      title={`Identificados (${groups.reduce((sum, group) => sum + group.lines.length, 0)})`}
      description="Reconhecidos pelo dicionário ou pelas suas regras. Abra um grupo para trocar a categoria."
      action={
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          Lembrar as trocas para as próximas faturas
        </label>
      }
    >
      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma compra reconhecida ainda.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {groups.map((group) => (
            <li key={group.category.id}>
              <details className="rounded-lg border p-3">
                <summary className="flex cursor-pointer flex-wrap justify-between gap-2">
                  <span className="font-medium">
                    {group.category.icon} {group.category.name}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {group.lines.length} lançamento(s) · {formatCents(group.totalCents)}
                  </span>
                </summary>
                <ul className="mt-3 flex flex-col gap-2">
                  {group.lines.map((line) => (
                    <li key={line.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <span className="min-w-0 truncate">
                        {formatDate(line.date)} · {line.description} · {formatCents(line.amount_cents)}
                      </span>
                      {line.status === 'imported' ? (
                        <Badge variant="secondary">Lançado</Badge>
                      ) : (
                        <CategorySelect
                          categories={categories}
                          value={line.category_id}
                          label={`Categoria de ${line.description}`}
                          onChange={(value) => void change(line, value)}
                        />
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
