import { RefreshCw, AlertTriangle } from 'lucide-react'

/* ═══════════════════════════════════════════════════════════════════════ */
/*  SPINNER                                                                */
/* ═══════════════════════════════════════════════════════════════════════ */

export function Spinner({ size = 'md' }) {
  const s = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-8 h-8' : 'w-6 h-6'
  return (
    <div className={`${s} border-2 border-brand-500/20 border-t-brand-500 rounded-full animate-spin`} />
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  SKELETON LOADER                                                        */
/* ═══════════════════════════════════════════════════════════════════════ */

export function SkeletonCard({ className = '' }) {
  return (
    <div className={`glass-card p-5 space-y-3 animate-fade-in ${className}`} aria-hidden="true">
      <div className="skeleton h-3 w-24" />
      <div className="skeleton h-7 w-16" />
      <div className="skeleton h-2.5 w-32" />
    </div>
  )
}

export function SkeletonRow() {
  return (
    <div className="glass-card p-4 flex items-center gap-4 animate-fade-in" aria-hidden="true">
      <div className="skeleton h-3 w-20" />
      <div className="flex-1 flex items-center gap-3">
        <div className="skeleton h-4 w-28 ml-auto" />
        <div className="skeleton h-5 w-12" />
        <div className="skeleton h-4 w-28" />
      </div>
      <div className="skeleton h-5 w-16" />
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  LOADING STATE                                                          */
/* ═══════════════════════════════════════════════════════════════════════ */

export function LoadingState({ message = 'Loading...' }) {
  return (
    <div className="space-y-3" role="status" aria-label={message}>
      <div className="flex flex-col items-center justify-center py-16 gap-4">
        <div className="relative">
          <div className="w-10 h-10 border-2 border-brand-500/20 border-t-brand-500 rounded-full animate-spin" />
          <div className="absolute inset-0 w-10 h-10 border-2 border-transparent border-b-brand-300/30 rounded-full animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
        </div>
        <span className="text-slate-400 text-sm font-medium">{message}</span>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  ERROR STATE                                                            */
/* ═══════════════════════════════════════════════════════════════════════ */

export function ErrorState({ message = 'An error occurred', retry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4" role="alert">
      <div className="w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
        <AlertTriangle className="w-7 h-7 text-rose-400" />
      </div>
      <div className="text-center">
        <div className="text-slate-200 font-semibold">{message}</div>
        <div className="text-slate-400 text-sm mt-1">Please try again or check your connection.</div>
      </div>
      {retry && (
        <button
          className="btn-secondary mt-1 text-sm inline-flex items-center gap-2"
          onClick={retry}
          aria-label="Retry loading"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry
        </button>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════ */
/*  EMPTY STATE                                                            */
/* ═══════════════════════════════════════════════════════════════════════ */

export function EmptyState({ message = 'No data available', icon = '📭' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <div className="w-14 h-14 rounded-2xl bg-slate-800/50 border border-slate-700/50 flex items-center justify-center text-2xl">
        {icon}
      </div>
      <div className="text-slate-400 text-sm font-medium">{message}</div>
    </div>
  )
}
