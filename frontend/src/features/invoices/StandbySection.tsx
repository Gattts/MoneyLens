import { useState } from 'react'
import { toast } from 'sonner'

import { SectionCard } from '@/components/page'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { useSingleFlight } from '@/hooks/useSingleFlight'
import { api } from '@/lib/api'
import { Amount } from '@/components/money-display'
import type { Category, InvoiceLine } from '@/lib/types'

import { CategorySelect } from './CategorySelect'
import { type MerchantGroup, groupPending } from './invoice-groups'

function StandbyRow({
  group,
  categories,
  onChanged,
}: {
  group: MerchantGroup
  categories: Category[]
  onChanged: () => void
}) {
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [remember, setRemember] = useState(true)
  const [error, setError] = useState<string>()
  const resolving = useSingleFlight()
  const ignoring = useSingleFlight()
  const label = group.kind === 'income' ? `${group.description} (entrada)` : group.description

  function resolve() {
    if (categoryId === null) {
      setError('Escolha a categoria.')
      return
    }
    void resolving.run(async () => {
      try {
        // Com "lembrar", o servidor aprende a regra e resolve sozinho as outras linhas iguais.
        const targets = remember ? group.lines.slice(0, 1) : group.lines
        for (const line of targets) await api.invoiceLines.update(line.id, { category_id: categoryId, remember })
        toast.success(`“${group.description}” resolvido.`)
        onChanged()
      } catch (failure) {
        toast.error(failure instanceof Error ? failure.message : 'Não foi possível resolver.')
      }
    })
  }

  function skip() {
    void ignoring.run(async () => {
      try {
        for (const line of group.lines) await api.invoiceLines.ignore(line.id)
        toast.success(`“${group.description}” fica fora da importação.`)
        onChanged()
      } catch (failure) {
        toast.error(failure instanceof Error ? failure.message : 'Não foi possível tirar da importação.')
      }
    })
  }

  return (
    <li className="flex flex-col gap-2 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate font-medium">{label}</p>
        <p className="text-sm text-muted-foreground">
          <span>{group.lines.length}×</span> · <Amount cents={group.totalCents} kind={group.kind} />
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <CategorySelect
          categories={categories}
          kind={group.kind}
          value={categoryId}
          label={`Categoria de ${label}`}
          invalid={Boolean(error)}
          onChange={(value) => {
            setCategoryId(value)
            setError(undefined)
          }}
        />
        <label className="flex items-center gap-1 text-sm">
          <input
            type="checkbox"
            className="size-4"
            checked={remember}
            aria-label={`Lembrar ${label} nas próximas faturas`}
            onChange={(event) => setRemember(event.target.checked)}
          />
          lembrar
        </label>
        <Button size="sm" disabled={resolving.pending || ignoring.pending} onClick={resolve}>
          {resolving.pending ? <Spinner /> : null} Resolver
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={resolving.pending || ignoring.pending}
          aria-label={`Não lançar ${label}`}
          onClick={skip}
        >
          Não lançar
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </li>
  )
}

export function StandbySection({
  lines,
  categories,
  onChanged,
}: {
  lines: InvoiceLine[]
  categories: Category[]
  onChanged: () => void
}) {
  const groups = groupPending(lines)
  return (
    <SectionCard
      title={`Em standby (${groups.reduce((sum, group) => sum + group.lines.length, 0)})`}
      description="Não reconhecidos. Escolha a categoria; com “lembrar”, as próximas importações já reconhecem."
    >
      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nada em standby.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {groups.map((group) => (
            <StandbyRow key={group.key} group={group} categories={categories} onChanged={onChanged} />
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
