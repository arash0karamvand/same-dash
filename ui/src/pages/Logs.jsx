import { useCallback, useEffect, useState } from 'react'
import { auditApi } from '../api/client'
import Select from '../components/Select'
import { Button, Card, EmptyState, Field, FilterBar, LoadMoreButton } from '../components/ui'
import { PAGE_SIZE } from '../config/pagination'
import { formatDate } from '../utils/format'
import { fromLegacy } from '../styles/tw.js'

export default function Logs() {
  const [logs, setLogs] = useState([])
  const [actions, setActions] = useState([])
  const [entityTypes, setEntityTypes] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [action, setAction] = useState('')
  const [entityType, setEntityType] = useState('')
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
        entity_type: entityType || undefined,
        search: search.trim() || undefined,
      })
      setLogs((prev) => (append ? [...prev, ...data.results] : data.results))
      setTotal(data.total)
      setOffset(nextOffset)
      if (data.actions?.length) setActions(data.actions)
      if (data.entity_types?.length) setEntityTypes(data.entity_types)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [action, entityType, search])

  useEffect(() => {
    load({ offset: 0 })
  }, [load])

  return (
    <div className={fromLegacy("page")}>
      <Card title="لاگ فعالیت‌ها">
        {error && <div className={fromLegacy("alert-error")}>{error}</div>}
        <FilterBar>
          <Field label="نوع عملیات">
            <Select
              value={action}
              onChange={setAction}
              options={[{ value: '', label: 'همه' }, ...actions]}
              placeholder="همه"
            />
          </Field>
          <Field label="نوع موجودیت">
            <Select
              value={entityType}
              onChange={setEntityType}
              options={[{ value: '', label: 'همه' }, ...entityTypes]}
              placeholder="همه"
            />
          </Field>
          <Field label="جستجو">
            <input
              className={fromLegacy("search-input")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="کاربر، شرح، نوع موجودیت…"
              onKeyDown={(e) => e.key === 'Enter' && load({ offset: 0 })}
            />
          </Field>
          <div className={fromLegacy("page-filters-actions")}>
            <Button type="button" onClick={() => load({ offset: 0 })}>اعمال فیلتر</Button>
          </div>
        </FilterBar>
        <p className={fromLegacy("muted")}>
          {total > 0 ? `${total.toLocaleString('fa-IR')} رکورد` : 'بدون رکورد'}
          {logs.some((l) => l.is_executive_only) && ' — شامل لاگ‌های محرمانه'}
        </p>
        {loading ? <div className={fromLegacy("loading")}>در حال بارگذاری…</div> : logs.length === 0 ? (
          <EmptyState text="لاگی ثبت نشده." />
        ) : (
          <>
            <div className={fromLegacy("table-wrap logs-table-desktop")}>
              <table className={fromLegacy("table")}>
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
            </div>
            <div className={fromLegacy("logs-cards-mobile")}>
              {logs.map((l) => (
                <div key={l.id} className={fromLegacy(`m-card${l.is_executive_only ? ' row-highlight' : ''}`)}>
                  <div className={fromLegacy("m-card-head")}>
                    <strong>{l.action_display}</strong>
                    <span className={fromLegacy("muted small")}>{formatDate(l.created_at)}</span>
                  </div>
                  <div className={fromLegacy("m-card-grid")}>
                    <div><span className={fromLegacy("muted")}>کاربر</span>{l.user_name}</div>
                    <div><span className={fromLegacy("muted")}>موجودیت</span>{l.entity_type || '—'}</div>
                  </div>
                  <p className={fromLegacy("muted small")} style={{ margin: '8px 0 0' }}>{l.message}{l.is_executive_only ? ' 🔒' : ''}</p>
                </div>
              ))}
            </div>
            <LoadMoreButton
              hasMore={logs.length < total}
              loading={loadingMore}
              onClick={() => load({ offset: offset + PAGE_SIZE, append: true })}
            />
          </>
        )}
      </Card>
    </div>
  )
}
