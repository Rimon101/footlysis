import { cn } from '../../lib/utils'

/**
 * BentoTile — a glassmorphic tile that occupies a configurable number
 * of columns across breakpoints.
 *
 * Defaults give a balanced 1/3-width tile on desktop.
 *
 * Props:
 * - span:    base col-span (default 12 = full width on mobile)
 * - sm:      col-span at sm (default 12 = full width on tablet)
 * - md:      col-span at md (default 6 = half on 6-col)
 * - lg:      col-span at lg (default 4 = third on 12-col)
 * - as:      element tag (default 'div')
 * - className: extra classes
 */
export function BentoTile({
  children,
  className,
  span = 12,
  sm,
  md = 6,
  lg = 4,
  as: Tag = 'div',
  plain = false,
  ...rest
}) {
  // Build col-span classes dynamically. Tailwind JIT picks up literals that
  // appear in source — we also have a safelist in tailwind.config.js.
  const colClass = `col-span-${span}`
  const smClass  = sm  != null ? `sm:col-span-${sm}`  : null
  const mdClass  = md != null ? `md:col-span-${md}`  : null
  const lgClass  = lg != null ? `lg:col-span-${lg}`  : null

  return (
    <Tag
      className={cn(
        plain ? '' : 'tile p-5 sm:p-6',
        'animate-bento-in',
        colClass,
        smClass,
        mdClass,
        lgClass,
        className
      )}
      {...rest}
    >
      {children}
    </Tag>
  )
}
