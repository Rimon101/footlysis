import { TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'

/* ═══════════════════════════════════════════════════════════════════════ */
/*  STAT CARD                                                              */
/* ═══════════════════════════════════════════════════════════════════════ */

export function StatCard({ label, value, sub, trend, color = 'white', icon: Icon, link }) {
  const trendIcon = trend > 0
    ? <TrendingUp className="w-3.5 h-3.5 text-brand-400" />
    : trend < 0
    ? <TrendingDown className="w-3.5 h-3.5 text-rose-400" />
    : <Minus className="w-3.5 h-3.5 text-slate-500" />

  const Wrapper = link ? Link : 'div'
  const wrapperProps = link ? { to: link } : {}

  const valueColor =
    color === 'green'  ? 'text-brand-400'  :
    color === 'red'    ? 'text-rose-400'   :
    color === 'yellow' ? 'text-amber-400'  :
    'text-white'

  return (
    <Wrapper
      {...wrapperProps}
      className={`metric-card group${link ? ' cursor-pointer' : ''}`}
      aria-label={link ? `${label}: ${value}` : undefined}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400 uppercase tracking-wider font-medium">{label}</span>
        {Icon && (
          <div className="w-8 h-8 rounded-lg bg-brand-500/10 flex items-center justify-center group-hover:bg-brand-500/20 transition-colors">
            <Icon className="w-4 h-4 text-brand-400" />
          </div>
        )}
      </div>
      <div className={`text-2xl font-bold font-mono mt-1 ${valueColor}`}>
        {value ?? '—'}
      </div>
      {(sub || trend !== undefined) && (
        <div className="flex items-center gap-1.5 mt-0.5">
          {trend !== undefined && trendIcon}
          {sub && <span className="text-xs text-slate-400">{sub}</span>}
        </div>
      )}
    </Wrapper>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  PROBABILITY BAR                                                        */
/* ═══════════════════════════════════════════════════════════════════════ */

export function ProbBar({ label, probability, color = 'brand', showPct = true }) {
  const pct = Math.round((probability || 0) * 100)
  const barColors = {
    brand:  'from-brand-500 to-brand-400',
    yellow: 'from-amber-500 to-amber-400',
    red:    'from-rose-500 to-rose-400',
    blue:   'from-cyan-500 to-cyan-400',
  }

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-slate-400 font-medium">{label}</span>
        {showPct && <span className="font-mono font-bold text-white">{pct}%</span>}
      </div>
      <div className="h-2 bg-white/[0.06] rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${barColors[color] || barColors.brand} rounded-full transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  FORM BADGES                                                            */
/* ═══════════════════════════════════════════════════════════════════════ */

export function FormBadge({ result }) {
  const cls = result === 'W' ? 'form-W' : result === 'D' ? 'form-D' : 'form-L'
  return (
    <span className={`stat-badge ${cls} w-7 h-7 text-[11px]`}>{result}</span>
  )
}

export function FormRow({ form = '' }) {
  return (
    <div className="flex gap-1" role="list" aria-label="Recent form">
      {form.split('').map((r, i) => <FormBadge key={i} result={r} />)}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  PAGE HEADER                                                            */
/* ═══════════════════════════════════════════════════════════════════════ */

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
      <div className="min-w-0">
        <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{title}</h1>
        {subtitle && <p className="text-slate-400 text-sm mt-1">{subtitle}</p>}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  BADGE                                                                  */
/* ═══════════════════════════════════════════════════════════════════════ */

export function Badge({ children, variant = 'default' }) {
  const variants = {
    default: 'bg-white/[0.08] text-slate-300 border border-white/[0.08]',
    green:   'bg-brand-500/15 text-brand-300 border border-brand-400/25',
    red:     'bg-rose-500/15 text-rose-400 border border-rose-400/25',
    yellow:  'bg-amber-500/15 text-amber-300 border border-amber-400/25',
    blue:    'bg-cyan-500/15 text-cyan-300 border border-cyan-400/25',
  }
  return (
    <span className={`inline-block text-xs font-semibold px-2.5 py-0.5 rounded-full ${variants[variant]}`}>
      {children}
    </span>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  SECTION TITLE                                                          */
/* ═══════════════════════════════════════════════════════════════════════ */

export function SectionTitle({ children }) {
  return (
    <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
      <span className="w-1 h-4 rounded-full bg-brand-500" />
      {children}
    </h2>
  )
}
