import { useEffect, useRef } from 'react'

export function usePolling(fn, intervalMs, stopWhen = () => false) {
  const fnRef = useRef(fn)
  const stopRef = useRef(stopWhen)
  useEffect(() => { fnRef.current = fn }, [fn])
  useEffect(() => { stopRef.current = stopWhen }, [stopWhen])

  useEffect(() => {
    if (!intervalMs || intervalMs <= 0) return undefined
    let active = true
    let timer
    const poll = async () => {
      if (!active || stopRef.current()) return
      await fnRef.current()
      if (active && !stopRef.current()) timer = window.setTimeout(poll, intervalMs)
    }
    timer = window.setTimeout(poll, intervalMs)
    return () => { active = false; window.clearTimeout(timer) }
  }, [intervalMs])
}
