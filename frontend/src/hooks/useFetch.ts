import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../services/api'

export interface FetchState<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
  setData: (value: T | null | ((prev: T | null) => T | null)) => void
}

/**
 * Runs `fn` on mount and whenever `deps` change. Results from superseded calls are ignored, so a
 * slow earlier response can never overwrite a newer one. `reload()` refetches without clearing data.
 */
export function useFetch<T>(fn: () => Promise<T>, deps: unknown[]): FetchState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const latest = useRef(0)
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    const id = ++latest.current
    setLoading(true)
    fnRef
      .current()
      .then((result) => {
        if (id !== latest.current) return
        setData(result)
        setError(null)
      })
      .catch((err: unknown) => {
        if (id !== latest.current) return
        setError(err instanceof ApiError ? err : new ApiError(0, 'unknown', 'Something went wrong'))
      })
      .finally(() => {
        if (id === latest.current) setLoading(false)
      })
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload, setData }
}
