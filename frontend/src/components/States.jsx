// Spinner
export function Spinner({ size = 'md' }) {
  const s = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-8 h-8' : 'w-6 h-6'
  return (
    <div className={`${s} border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin`} />
  )
}

// Loading State
export function LoadingState({ message = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <Spinner size="lg" />
      <span className="text-slate-400 text-sm">{message}</span>
    </div>
  )
}

// Error State
export function ErrorState({ message = 'An error occurred', retry }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3">
      <div className="text-red-400 text-4xl">⚠</div>
      <div className="text-slate-300 font-medium">{message}</div>
      {retry && (
        <button className="btn-secondary mt-2 text-sm" onClick={retry}>
          Retry
        </button>
      )}
    </div>
  )
}

// Empty State
export function EmptyState({ message = 'No data available', icon = '📭' }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-2">
      <div className="text-4xl">{icon}</div>
      <div className="text-slate-400 text-sm">{message}</div>
    </div>
  )
}
