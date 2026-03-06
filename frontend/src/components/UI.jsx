import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Link } from 'react-router-dom'

export function StatCard({ label, value, sub, trend, color = 'white', icon: Icon, link }) {
  const trendIcon = trend > 0
    ? <TrendingUp className="w-3.5 h-3.5 text-brand-400" />
    : trend < 0
    ? <TrendingDown className="w-3.5 h-3.5 text-red-400" />
    : <Minus className="w-3.5 h-3.5 text-slate-500" />

  const Wrapper = link ? Link : 'div'
  const wrapperProps = link ? { to: link } : {}

  return (
    <Wrapper {...wrapperProps} className={`metric-card${link ? ' cursor-pointer hover:border-brand-500/40 hover:bg-white/[0.04] transition-all' : ''}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400 uppercase tracking-wider">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-slate-500" />}
      </div>
      <div className={`text-2xl font-bold mt-1 ${color === 'green' ? 'text-brand-400' : color === 'red' ? 'text-red-400' : color === 'yellow' ? 'text-yellow-400' : 'text-white'}`}>
        {value ?? '—'}
      </div>
      {(sub || trend !== undefined) && (
        <div className="flex items-center gap-1 mt-1">
          {trend !== undefined && trendIcon}
          {sub && <span className="text-xs text-slate-500">{sub}</span>}
        </div>
      )}
    </Wrapper>
  )
}

export function ProbBar({ label, probability, color = 'brand', showPct = true }) {
  const pct = Math.round((probability || 0) * 100)
  const barColor = color === 'brand'
    ? 'bg-brand-500'
    : color === 'yellow'
    ? 'bg-yellow-500'
    : color === 'red'
    ? 'bg-red-500'
    : 'bg-blue-500'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        {showPct && <span className="font-mono font-semibold text-white">{pct}%</span>}
      </div>
      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function FormBadge({ result }) {
  const cls = result === 'W' ? 'form-W' : result === 'D' ? 'form-D' : 'form-L'
  return (
    <span className={`stat-badge ${cls} w-6 h-6 justify-center font-bold`}>{result}</span>
  )
}

export function FormRow({ form = '' }) {
  return (
    <div className="flex gap-1">
      {form.split('').map((r, i) => <FormBadge key={i} result={r} />)}
    </div>
  )
}

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-3 mb-6 flex-wrap">
      <div className="min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold text-white">{title}</h1>
        {subtitle && <p className="text-slate-400 text-sm mt-0.5">{subtitle}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}

export function Badge({ children, variant = 'default' }) {
  const variants = {
    default: 'bg-white/10 text-slate-300',
    green: 'bg-brand-500/20 text-brand-400 border border-brand-500/30',
    red: 'bg-red-500/20 text-red-400 border border-red-500/30',
    yellow: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
    blue: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
  }
  return (
    <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${variants[variant]}`}>
      {children}
    </span>
  )
}

export function SectionTitle({ children }) {
  return (
    <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
      {children}
    </h2>
  )
}
