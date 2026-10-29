import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import type { Category } from '@/lib/types'

/** Só categorias ativas do tipo da linha: entrada vira receita, e saída (ou compra no cartão), despesa. */
export function CategorySelect({
  categories,
  kind = 'expense',
  value,
  label,
  onChange,
  invalid,
}: {
  categories: Category[]
  kind?: Category['kind']
  value: number | null
  label: string
  onChange: (categoryId: number | null) => void
  invalid?: boolean
}) {
  const options = categories.filter((item) => item.kind === kind && !item.archived)
  return (
    <NativeSelect
      aria-label={label}
      aria-invalid={invalid ? true : undefined}
      value={value === null ? '' : String(value)}
      onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
    >
      <NativeSelectOption value="">Categoria…</NativeSelectOption>
      {options.map((item) => (
        <NativeSelectOption key={item.id} value={String(item.id)}>
          {item.icon} {item.name}
        </NativeSelectOption>
      ))}
    </NativeSelect>
  )
}
