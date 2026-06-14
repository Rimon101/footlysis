import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Calendar, TrendingUp,
  Table2, BookOpen, Settings2,
} from 'lucide-react'
import { cn } from '../lib/utils'

/**
 * MobileNav — glassmorphic bottom tab bar.
 * Hidden on lg+ (1024px+). Active pill = cyan with glow.
 * Includes safe-area-inset-bottom padding for notched devices.
 */
const tabs = [
  { to: '/',            label: 'Home',     icon: LayoutDashboard, end: true },
  { to: '/matches',     label: 'Matches',  icon: Calendar },
  { to: '/predictions', label: 'Predict',  icon: TrendingUp },
  { to: '/standings',   label: 'Table',    icon: Table2 },
  { to: '/blogs',       label: 'Blogs',    icon: BookOpen },
  { to: '/settings',    label: 'Settings', icon: Settings2 },
]

export default function MobileNav() {
  return (
    <nav
      aria-label="Primary"
      className="lg:hidden fixed bottom-0 inset-x-0 z-30 px-3 pt-2"
      style={{ paddingBottom: 'max(env(safe-area-inset-bottom), 8px)' }}
    >
      <div className="glass-card flex justify-between items-stretch px-1.5 py-1.5 gap-1">
        {tabs.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex-1 flex flex-col items-center gap-0.5 py-1.5 rounded-xl transition-all min-w-0',
                'min-h-[44px] justify-center',
                isActive
                  ? 'bg-brand-500/15 text-brand-500 shadow-glow-cyan-sm'
                  : 'text-slate-400 hover:text-slate-200 active:bg-white/[0.04]'
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className="w-5 h-5 flex-shrink-0" />
                <span className="text-[10px] font-medium tracking-wide truncate">
                  {label}
                </span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
