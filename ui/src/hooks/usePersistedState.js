import { useCallback, useState } from 'react'

function readStored(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    const parsed = JSON.parse(raw)
    return parsed ?? fallback
  } catch {
    return fallback
  }
}

export function usePersistedState(key, initialValue) {
  const [value, setValue] = useState(() => readStored(key, initialValue))

  const setPersisted = useCallback((next) => {
    setValue((prev) => {
      const resolved = typeof next === 'function' ? next(prev) : next
      try {
        localStorage.setItem(key, JSON.stringify(resolved))
      } catch {
        /* ignore quota errors */
      }
      return resolved
    })
  }, [key])

  return [value, setPersisted]
}
