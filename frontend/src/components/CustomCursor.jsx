import { useEffect, useState, useRef } from 'react'

export default function CustomCursor() {
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isHovering, setIsHovering] = useState(false)
  const [isVisible, setIsVisible] = useState(false)
  const [isMobile, setIsMobile] = useState(false)

  const ringRef = useRef(null)
  const dotRef = useRef(null)
  const requestRef = useRef()
  const mouseRef = useRef({ x: 0, y: 0 })

  useEffect(() => {
    // Detect mobile/touch
    const checkMobile = () => {
      setIsMobile(window.matchMedia('(hover: none)').matches)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)

    const onMouseMove = (e) => {
      mouseRef.current = { x: e.clientX, y: e.clientY }
      if (!isVisible) setIsVisible(true)
    }

    const onMouseDown = () => setIsHovering(true)
    const onMouseUp = () => setIsHovering(false)

    const handleHoverStart = (e) => {
      if (e.target.closest('button, a, select, [role="button"]')) {
        setIsHovering(true)
      }
    }

    const handleHoverEnd = (e) => {
      if (e.target.closest('button, a, select, [role="button"]')) {
        setIsHovering(false)
      }
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mouseup', onMouseUp)
    window.addEventListener('mouseover', handleHoverStart)
    window.addEventListener('mouseout', handleHoverEnd)

    const animate = () => {
      // Smooth interpolation for the ring
      const ringX = parseFloat(ringRef.current?.style?.getPropertyValue('--x') || mouseRef.current.x)
      const ringY = parseFloat(ringRef.current?.style?.getPropertyValue('--y') || mouseRef.current.y)

      const nextX = ringX + (mouseRef.current.x - ringX) * 0.15
      const nextY = ringY + (mouseRef.current.y - ringY) * 0.15

      if (ringRef.current) {
        ringRef.current.style.setProperty('--x', `${nextX}px`)
        ringRef.current.style.setProperty('--y', `${nextY}px`)
        ringRef.current.style.transform = `translate3d(calc(${nextX}px - 50%), calc(${nextY}px - 50%), 0)`
      }

      if (dotRef.current) {
        dotRef.current.style.transform = `translate3d(calc(${mouseRef.current.x}px - 50%), calc(${mouseRef.current.y}px - 50%), 0)`
      }

      requestRef.current = requestAnimationFrame(animate)
    }

    requestRef.current = requestAnimationFrame(animate)

    return () => {
      window.removeEventListener('resize', checkMobile)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mouseup', onMouseUp)
      window.removeEventListener('mouseover', handleHoverStart)
      window.removeEventListener('mouseout', handleHoverEnd)
      cancelAnimationFrame(requestRef.current)
    }
  }, [isVisible])

  if (isMobile) return null

  return (
    <>
      <div
        ref={ringRef}
        className={`custom-cursor-ring ${isHovering ? 'expanded' : ''} ${isVisible ? 'visible' : ''}`}
      />
      <div
        ref={dotRef}
        className={`custom-cursor-dot ${isHovering ? 'active' : ''} ${isVisible ? 'visible' : ''}`}
      />
    </>
  )
}
