import {
  ArrowLeftRightIcon,
  CalendarRangeIcon,
  CreditCardIcon,
  FileTextIcon,
  LayoutDashboardIcon,
  LogOutIcon,
  MenuIcon,
  RepeatIcon,
  SettingsIcon,
  TagsIcon,
  TargetIcon,
  WalletIcon,
} from 'lucide-react'
import { Suspense, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'

import { LoadingBlock } from '@/components/query-state'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useAuth } from '@/features/auth/auth-context'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/', label: 'Painel', icon: LayoutDashboardIcon },
  { to: '/lancamentos', label: 'Lançamentos', icon: ArrowLeftRightIcon },
  { to: '/fixas', label: 'Fixas', icon: RepeatIcon },
  { to: '/cartoes', label: 'Cartões', icon: CreditCardIcon },
  { to: '/faturas', label: 'Faturas', icon: FileTextIcon },
  { to: '/metas', label: 'Metas', icon: TargetIcon },
  { to: '/categorias', label: 'Categorias', icon: TagsIcon },
  { to: '/anual', label: 'Balanço anual', icon: CalendarRangeIcon },
  { to: '/configuracoes', label: 'Configurações', icon: SettingsIcon },
]
const PAGES_WITH_MONTH = new Set(['/', '/lancamentos'])

function Brand() {
  return (
    <div className="flex items-center gap-2 font-semibold">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <WalletIcon className="size-4" aria-hidden />
      </span>
      Financeiro
    </div>
  )
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation()
  // O mês escolhido acompanha a navegação entre Painel e Lançamentos.
  const month = new URLSearchParams(location.search).get('mes')
  return (
    <nav aria-label="Principal" className="flex flex-col gap-1">
      {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={{ pathname: to, search: month && PAGES_WITH_MONTH.has(to) ? `?mes=${month}` : '' }}
          end={to === '/'}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )
          }
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

function UserFooter() {
  const { user, logout } = useAuth()
  return (
    <div className="flex items-center justify-between gap-2 border-t pt-3 text-sm">
      <span className="truncate text-muted-foreground" title={user.username}>
        {user.username}
      </span>
      <Button variant="ghost" size="sm" title="Encerra a sessão em todos os aparelhos" onClick={() => void logout()}>
        <LogOutIcon /> Sair
      </Button>
    </div>
  )
}

export function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  return (
    <div className="min-h-svh bg-muted/30 md:grid md:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-svh flex-col gap-6 border-r bg-background p-4 md:flex">
        <Brand />
        <div className="flex-1">
          <Navigation />
        </div>
        <UserFooter />
      </aside>
      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-background/95 px-4 py-2 backdrop-blur md:hidden">
          <Brand />
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Abrir menu">
                <MenuIcon />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="flex w-72 flex-col gap-6 p-4">
              <SheetHeader className="p-0">
                <SheetTitle>
                  <Brand />
                </SheetTitle>
                <SheetDescription className="sr-only">Navegação principal</SheetDescription>
              </SheetHeader>
              <div className="flex-1">
                <Navigation onNavigate={() => setMenuOpen(false)} />
              </div>
              <UserFooter />
            </SheetContent>
          </Sheet>
        </header>
        <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 p-4 md:p-8">
          <Suspense fallback={<LoadingBlock rows={6} />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
