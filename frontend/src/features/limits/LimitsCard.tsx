import { Link } from 'react-router'

import { SectionCard } from '@/components/page'
import { Button } from '@/components/ui/button'
import { useLimits } from '@/lib/queries'

import { LimitBar } from './LimitBar'

const SHOWN = 5

/** Os tetos ativos de maior percentual no Painel (a API já manda nessa ordem). */
export function LimitsCard() {
  const limits = useLimits()
  const shown = (limits.data ?? []).filter((limit) => limit.active).slice(0, SHOWN)
  if (shown.length === 0) return null
  return (
    <SectionCard
      title="Tetos do mês"
      action={
        <Button asChild variant="ghost" size="sm">
          <Link to="/tetos">Ver tetos</Link>
        </Button>
      }
    >
      <ul className="flex flex-col gap-4">
        {shown.map((limit) => (
          <li key={limit.id} className="flex flex-col gap-1.5">
            <span className="flex items-center gap-1.5 text-sm font-medium">
              {limit.icon && <span aria-hidden>{limit.icon}</span>}
              <span>{limit.name}</span>
            </span>
            <LimitBar limit={limit} />
          </li>
        ))}
      </ul>
    </SectionCard>
  )
}
