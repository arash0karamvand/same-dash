import { useCallback, useEffect, useState } from 'react'
import { auditApi } from '../api/client'
import Select from '../components/Select'
import { Button, Card, EmptyState, Field, FilterBar } from '../components/ui'
import { formatDate } from '../utils/format'

const PAGE_SIZE = 200

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [actions, setActions] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async (opts = {}) => {
    const nextOffset = opts.offset ?? 0
    const append = opts.append ?? false
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const data = await auditApi.list({
        offset: nextOffset,
        limit: PAGE_SIZE,
        action: action || undefined,
        search: search.trim() || undefined,
      })
      setLogs((prev) => (append ? [...prev, ...data.results] : data.results))
      setTotal(data.total)
      setOffset(nextOffset)
      if (data.actions?.length) setActions(data.actions)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [action, search])

  useEffect(() => {
    load({ offset: 0 })
  }, [load])

  const hasMore = logs.length < total

  return (
    <div className="page">
      <Card title="لاگ فعالیت‌ها">
        {error && <div className="alert-error">{error}</div>}
        <FilterBar>
          <Field label="نوع عملیات">
            <Select
              value={action}
              onChange={setAction}
              options={[{ value: '', label: 'همه' }, ...actions]}
              placeholder="همه"
            />
          </Field>
          <Field label="جستجو">
            <input
              className="search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="کاربر، شرح، نوع موجودیت…"
              onKeyDown={(e) => e.key === 'Enter' && load({ offset: 0 })}
            />
          </Field>
          <div className="page-filters-actions">
            <Button type="button" onClick={() => load({ offset: 0 })}>اعمال فیلتر</Button>
          </div>
        </FilterBar>
        <p className="muted">
          {total > 0 ? `${total.toLocaleString('fa-IR')} رکورد` : 'بدون رکورد'}
          {logs.some((l) => l.is_executive_only) && ' — شامل لاگ‌های محرمانه'}
        </p>
        {loading ? <div className="loading">در حال بارگذاری…</div> : logs.length === 0 ? (
          <EmptyState text="لاگی ثبت نشده." />
        ) : (
          <>
            <table className="table">
              <thead>
                <tr><th>زمان</th><th>کاربر</th><th>عملیات</th><th>موجودیت</th><th>شرح</th></tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className={l.is_executive_only ? 'row-highlight' : ''}>
                    <td>{formatDate(l.created_at)}</td>
                    <td>{l.user_name}</td>
                    <td>{l.action_display}</td>
                    <td>{l.entity_type || '—'}</td>
                    <td>{l.message}{l.is_executive_only ? ' 🔒' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {hasMore && (
              <div className="form-actions" style={{ marginTop: 16 }}>
                <Button
                  type="button"
                  disabled={loadingMore}
                  onClick={() => load({ offset: offset + PAGE_SIZE, append: true })}
                >
                  {loadingMore ? 'در حال بارگذاری…' : 'نمایش بیشتر'}
                </Button>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
