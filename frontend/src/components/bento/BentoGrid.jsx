import { cn } from '../../lib/utils'

/**
 * BentoGrid — 12-column responsive grid.
 * - mobile (<md): single-column reflow
 * - md (≥768): 6 columns
 * - lg (≥1024): 12 columns
 *
 * Use with <BentoTile> children that declare their own col-span.
 */
export function BentoGrid({ children, className }) {
  return (
    <div
      className={cn(
        'grid gap-6',
        'grid-cols-1',
        'md:grid-cols-6',
        'lg:grid-cols-12',
        'auto-rows-min',
        className
      )}
    >
      {children}
    </div>
  )
}
