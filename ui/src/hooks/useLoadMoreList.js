import { useCallback, useState } from 'react'
import { PAGE_SIZE } from '../config/pagination'

export function useLoadMoreList({ pageSize = PAGE_SIZE } = {}) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  const begin = useCallback((append = false) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
  }, [])

  const finish = useCallback(() => {
    setLoading(false)
    setLoadingMore(false)
  }, [])

  const applyPage = useCallback((data, { append = false } = {}) => {
    const results = Array.isArray(data?.results) ? data.results : []
    setItems((prev) => (append ? [...prev, ...results] : results))
    setTotal(Number(data?.total) || 0)
    setOffset(Number(data?.offset) || 0)
    return data
  }, [])

  const reset = useCallback(() => {
    setItems([])
    setTotal(0)
    setOffset(0)
  }, [])

  const hasMore = items.length < total
  const nextOffset = offset + pageSize

  return {
    items,
    setItems,
    total,
    offset,
    nextOffset,
    loading,
    loadingMore,
    begin,
    finish,
    applyPage,
    reset,
    hasMore,
    pageSize,
  }
}
