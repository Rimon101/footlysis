import { cn } from '../../lib/utils'

/**
 * BentoHeader — eyebrow + title + subtitle + optional right slot.
 * Uses Insight Elite type scale: Geist for title, label-caps for eyebrow.
 */
export function BentoHeader({ eyebrow, title, subtitle, right, className }) {
  return (
    <div className={cn('flex items-start justify-between gap-3 mb-4', className)}>
      <div className="min-w-0">
        {eyebrow && (
          <div className="text-[11px] uppercase tracking-[0.05em] font-bold text-brand-500 mb-1 font-sans">
            {eyebrow}
          </div>
        )}
        <h3 className="text-base sm:text-lg font-display font-semibold text-white leading-snug">
          {title}
        </h3>
        {subtitle && (
          <p className="text-sm text-slate-400 mt-1 leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>
      {right && <div className="flex-shrink-0">{right}</div>}
    </div>
  )
}
