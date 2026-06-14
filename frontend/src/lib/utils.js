import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Combine class names with Tailwind-aware conflict resolution.
 * Use this for any conditional / array / object class composition.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
