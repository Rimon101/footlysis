import { useEffect, useState, useRef } from 'react'

export default function CustomCursor() {
  const [isVisible, setIsVisible] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  const cursorRef = useRef(null)
  const requestRef = useRef()
  
  // Target values (what we want to reach)
  const target = useRef({
    x: 0, y: 0,
    width: 10, height: 10,
    borderRadius: 50,
    opacity: 0,
    backgroundColor: 'rgba(150, 150, 150, 0.6)',
    isHovering: false
  })

  // Current animated values (where we are now)
  const current = useRef({
    x: 0, y: 0,
    width: 10, height: 10,
    borderRadius: 50,
    opacity: 0
  })

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.matchMedia('(hover: none)').matches)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)

    const onMouseMove = (e) => {
      if (!target.current.isHovering) {
        target.current.x = e.clientX
        target.current.y = e.clientY
        target.current.width = 10
        target.current.height = 10
        target.current.borderRadius = 100 // circular
        target.current.backgroundColor = 'rgba(255, 255, 255, 0.95)'
      }
      if (!isVisible) setIsVisible(true)
      target.current.opacity = 1
    }

    const handleHoverStart = (e) => {
      const el = e.target.closest('button, a, select, [role="button"]')
      if (el) {
        const rect = el.getBoundingClientRect()
        target.current.isHovering = true
        target.current.x = rect.left + rect.width / 2
        target.current.y = rect.top + rect.height / 2
        target.current.width = rect.width + 12
        target.current.height = rect.height + 8
        
        // Get border radius from element, fallback to boxy 8px
        const style = window.getComputedStyle(el)
        target.current.borderRadius = parseInt(style.borderRadius) || 8
        target.current.backgroundColor = 'rgba(255, 255, 255, 0.3)'
      }
    }

    const handleHoverEnd = (e) => {
        const el = e.target.closest('button, a, select, [role="button"]')
        if (el) {
            target.current.isHovering = false
        }
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseover', handleHoverStart)
    window.addEventListener('mouseout', handleHoverEnd)

    const animate = () => {
      const lerp = (start, end, factor) => start + (end - start) * factor

      // Interpolate values (Higher factor = faster/snappier)
      current.current.x = lerp(current.current.x, target.current.x, 0.70)
      current.current.y = lerp(current.current.y, target.current.y, 0.70)
      current.current.width = lerp(current.current.width, target.current.width, 0.70)
      current.current.height = lerp(current.current.height, target.current.height, 0.70)
      current.current.opacity = lerp(current.current.opacity, target.current.opacity, 0.70)
      current.current.borderRadius = lerp(current.current.borderRadius, target.current.borderRadius, 0.70)

      if (cursorRef.current) {
        cursorRef.current.style.width = `${current.current.width}px`
        cursorRef.current.style.height = `${current.current.height}px`
        cursorRef.current.style.opacity = current.current.opacity
        cursorRef.current.style.backgroundColor = target.current.backgroundColor
        
        // Use pixels for both to avoid interpolation jumps between % and px
        // If it's a dot, borderRadius is half the min dimension
        const br = target.current.isHovering 
            ? current.current.borderRadius 
            : current.current.width / 2
            
        cursorRef.current.style.borderRadius = `${br}px`
        cursorRef.current.style.transform = `translate3d(calc(${current.current.x}px - 50%), calc(${current.current.y}px - 50%), 0)`
      }

      requestRef.current = requestAnimationFrame(animate)
    }

    requestRef.current = requestAnimationFrame(animate)

    return () => {
      window.removeEventListener('resize', checkMobile)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseover', handleHoverStart)
      window.removeEventListener('mouseout', handleHoverEnd)
      cancelAnimationFrame(requestRef.current)
    }
  }, [isVisible])

  if (isMobile) return null

  return (
    <div
      ref={cursorRef}
      className="magnetic-cursor"
    />
  )
}
