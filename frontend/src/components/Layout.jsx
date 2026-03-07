import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Calendar, Users, TrendingUp,
  BarChart2, Table2, Database, Activity, History, Menu, X
} from 'lucide-react'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/matches', label: 'Matches', icon: Calendar },
  { to: '/predictions', label: 'Predictions', icon: TrendingUp },
  { to: '/scrapes', label: 'Scrapes', icon: History },
  { to: '/teams', label: 'Teams', icon: Users },
  { to: '/standings', label: 'Standings', icon: Table2 },

  { to: '/data', label: 'Data Manager', icon: Database },
]

const linkClass = ({ isActive }) =>
  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${isActive
    ? 'bg-brand-500/20 text-brand-400 border border-brand-500/30'
    : 'text-slate-400 hover:text-white hover:bg-white/5'
  }`

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const close = () => setSidebarOpen(false)

  return (
    <div className="flex min-h-screen bg-pitch-dark">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-20 lg:hidden"
          onClick={close}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-30 w-64 flex-shrink-0 bg-pitch-dark border-r border-white/10 flex flex-col
        transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        lg:relative lg:translate-x-0
      `}>
        {/* Logo */}
        <div className="p-5 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
                <Activity className="w-4 h-4 text-white" />
              </div>
              <div>
                <div className="font-bold text-white text-lg leading-none">Footlysis</div>
                <div className="text-xs text-slate-500 mt-0.5">Pro Analytics</div>
              </div>
            </div>
            <button
              className="lg:hidden text-slate-400 hover:text-white p-1 rounded transition-colors"
              onClick={close}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={linkClass} end={to === '/'} onClick={close}>
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-white/10">
          <div className="glass-card p-3">
            <div className="text-xs text-slate-400">Model Active</div>
            <div className="text-sm font-semibold text-brand-400 mt-0.5">Dixon-Coles v1</div>
            <div className="flex gap-1 mt-2">
              <span className="stat-badge form-W text-xs">Poisson</span>
              <span className="stat-badge form-W text-xs">Elo</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content wrapper */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-pitch-dark sticky top-0 z-10">
          <button
            className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-white/10 transition-colors"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-brand-500 flex items-center justify-center">
              <Activity className="w-3 h-3 text-white" />
            </div>
            <span className="font-bold text-white text-sm">Footlysis</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <div className="p-4 sm:p-6 max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
