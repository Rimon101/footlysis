import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Calendar, TrendingUp,
  Table2, Settings2, Menu, X, Zap
} from 'lucide-react'

const mainNav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/matches', label: 'Matches', icon: Calendar },
  { to: '/predictions', label: 'Predictions', icon: TrendingUp },
  { to: '/standings', label: 'Standings', icon: Table2 },
]

const bottomNav = [
  { to: '/settings', label: 'Settings', icon: Settings2 },
]

function NavItem({ to, label, icon: Icon, end, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        `group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 relative ${
          isActive
            ? 'bg-brand-500/12 text-brand-400'
            : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
        }`
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-brand-500" />
          )}
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
            isActive
              ? 'bg-brand-500/15'
              : 'bg-white/[0.04] group-hover:bg-white/[0.06]'
          }`}>
            <Icon className="w-4 h-4" />
          </div>
          {label}
        </>
      )}
    </NavLink>
  )
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const close = () => setSidebarOpen(false)

  return (
    <div className="flex min-h-screen bg-pitch-dark overflow-hidden">
      {/* Skip to content — accessibility */}
      <a href="#main-content" className="skip-to-content">Skip to content</a>

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-20 lg:hidden"
          onClick={close}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-30 w-[260px] flex-shrink-0 flex flex-col
          bg-gradient-to-b from-[#060d1f] via-[#070e20] to-[#040a18]
          border-r border-white/[0.06]
          transition-transform duration-300 ease-out
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:relative lg:translate-x-0
        `}
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Logo */}
        <div className="p-5 pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-brand-500/15 border border-brand-500/20 flex items-center justify-center overflow-hidden">
                <img src="/logo.png" alt="Footlysis Logo" className="w-full h-full object-cover" />
              </div>
              <div>
                <div className="font-bold text-white text-lg leading-none tracking-tight">Footlysis</div>
                <div className="text-[11px] text-brand-400 font-medium mt-0.5 tracking-wide">PRO ANALYTICS</div>
              </div>
            </div>
            <button
              className="lg:hidden text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
              onClick={close}
              aria-label="Close navigation menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Divider with glow */}
        <div className="mx-4 h-px bg-gradient-to-r from-transparent via-brand-500/20 to-transparent" />

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto mt-2">
          {mainNav.map(item => (
            <NavItem key={item.to} {...item} end={item.to === '/'} onClick={close} />
          ))}

          {/* Separator */}
          <div className="my-4 mx-2 h-px bg-white/[0.04]" />

          {bottomNav.map(item => (
            <NavItem key={item.to} {...item} onClick={close} />
          ))}
        </nav>

        {/* Model status card */}
        <div className="p-4">
          <div className="glass-card p-3.5">
            <div className="flex items-center gap-2 mb-2">
              <Zap className="w-3.5 h-3.5 text-brand-400" />
              <span className="text-[11px] text-slate-400 uppercase tracking-wider font-medium">Model</span>
            </div>
            <div className="text-sm font-semibold text-white">Dixon-Coles v1</div>
            <div className="flex gap-1.5 mt-2">
              <span className="stat-badge form-W text-[10px] py-0.5">Poisson</span>
              <span className="stat-badge form-W text-[10px] py-0.5">Elo</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content wrapper */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-white/[0.06] bg-pitch-dark/95 backdrop-blur-xl sticky top-0 z-10">
          <button
            className="text-slate-400 hover:text-white p-2 rounded-xl hover:bg-white/10 transition-colors"
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg overflow-hidden">
              <img src="/logo.png" alt="Footlysis Logo" className="w-full h-full object-cover" />
            </div>
            <span className="font-bold text-white text-sm tracking-tight">Footlysis</span>
          </div>
        </header>

        {/* Page content */}
        <main id="main-content" className="flex-1 overflow-auto">
          <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
