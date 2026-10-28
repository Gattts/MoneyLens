import { SearchIcon } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { KIND_LABELS } from '@/lib/labels'
import type { Category, Kind } from '@/lib/types'

export interface FilterValues {
  search: string
  kind: Kind | ''
  categoryId: string
}

interface TransactionFiltersProps {
  values: FilterValues
  categories: Category[]
  onChange: (values: FilterValues) => void
}

export function TransactionFilters({ values, categories, onChange }: TransactionFiltersProps) {
  return (
    <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
      <div className="relative">
        <SearchIcon
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <Input
          aria-label="Buscar pela descrição"
          placeholder="Buscar pela descrição"
          className="pl-8"
          value={values.search}
          maxLength={100}
          onChange={(event) => onChange({ ...values, search: event.target.value })}
        />
      </div>
      <NativeSelect
        aria-label="Filtrar por tipo"
        className="w-full"
        value={values.kind}
        onChange={(event) => onChange({ ...values, kind: event.target.value as Kind | '' })}
      >
        <NativeSelectOption value="">Receitas e despesas</NativeSelectOption>
        <NativeSelectOption value="income">{KIND_LABELS.income}s</NativeSelectOption>
        <NativeSelectOption value="expense">{KIND_LABELS.expense}s</NativeSelectOption>
      </NativeSelect>
      <NativeSelect
        aria-label="Filtrar por categoria"
        className="w-full"
        value={values.categoryId}
        onChange={(event) => onChange({ ...values, categoryId: event.target.value })}
      >
        <NativeSelectOption value="">Todas as categorias</NativeSelectOption>
        {categories.map((category) => (
          <NativeSelectOption key={category.id} value={String(category.id)}>
            {`${category.icon} ${category.name}`.trim()}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </div>
  )
}
