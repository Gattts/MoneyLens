import { cn } from '@/lib/utils'

interface SegmentedControlProps<T extends string> {
  label: string
  name: string
  value: T
  options: ReadonlyArray<{ value: T; label: string }>
  onChange: (value: T) => void
}

/** Botões de opção única feitos com rádios nativos (teclado e leitor de tela funcionam de graça). */
export function SegmentedControl<T extends string>({
  label,
  name,
  value,
  options,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex w-full rounded-lg border bg-muted p-0.5">
      {options.map((option) => (
        <label
          key={option.value}
          className={cn(
            'flex-1 cursor-pointer rounded-md px-3 py-1.5 text-center text-sm font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring',
            value === option.value ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          <input
            type="radio"
            className="sr-only"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          {option.label}
        </label>
      ))}
    </div>
  )
}
