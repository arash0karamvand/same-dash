import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { recordFilterApi } from '../api/client'
import MoneyInput from './MoneyInput'
import PersianDateInput from './PersianDateInput'
import Select from './Select'
import { Button, EmptyState, Field, FilterBar, LoadMoreButton } from './ui'
import { formatDate, formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'

const EMPTY_FILTERS = {
  model: '',
  type_field: '',
  type: '',
  date_from: '',
  date_to: '',
  name: '',
  amount_min: '',
  amount_max: '',
  amount_field: '',
}

function buildInitialFilters(lockModel, defaultModel, initialFilters = {}) {
  const model = lockModel || defaultModel || ''
  const merged = { ...EMPTY_FILTERS, ...initialFilters, model }
  return merged
}

function buildQueryParams(filters, limit = 10, offset = 0) {
  if (!filters.model) return null
  const params = {
    model: filters.model,
    limit,
    offset,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    name: filters.name.trim() || undefined,
    amount_min: filters.amount_min !== '' ? filters.amount_min : undefined,
    amount_max: filters.amount_max !== '' ? filters.amount_max : undefined,
  }
  if (filters.type_field && filters.type) {
    params.type_field = filters.type_field
    params.type = filters.type
  }
  if (filters.amount_field && filters.amount_field !== 'default') {
    params.amount_field = filters.amount_field
  }
  return params
}

export default function RecordFilterPanel({
  scope,
  lockModel,
  defaultModel = '',
  liveSearch = true,
  debounceMs = 450,
  compact = false,
  unified = false,
  resultLimit = 10,
  hideResults = false,
  onFiltersChange,
  initialFilters = {},
  className = '',
}) {
  const initialFiltersKey = useMemo(
    () => JSON.stringify(initialFilters || {}),
    [initialFilters],
  )
  const parsedInitialFilters = useMemo(
    () => (initialFiltersKey ? JSON.parse(initialFiltersKey) : {}),
    [initialFiltersKey],
  )

  const [catalog, setCatalog] = useState(null)
  const [filters, setFilters] = useState(() =>
    buildInitialFilters(lockModel, defaultModel, parsedInitialFilters),
  )
  const [applied, setApplied] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [metaLoading, setMetaLoading] = useState(true)
  const [error, setError] = useState('')
  const requestSeq = useRef(0)

  useEffect(() => {
    setMetaLoading(true)
    recordFilterApi.catalog(scope)
      .then(setCatalog)
      .catch((e) => setError(e.message))
      .finally(() => setMetaLoading(false))
  }, [scope])

  useEffect(() => {
    setFilters(buildInitialFilters(lockModel, defaultModel, JSON.parse(initialFiltersKey || '{}')))
    setApplied(null)
    setError('')
  }, [lockModel, defaultModel, initialFiltersKey])

  useEffect(() => {
    if (!catalog?.models?.length || !filters.model) return
    const inCatalog = catalog.models.some((m) => m.key === filters.model)
    if (!inCatalog) {
      setError('این مدل در scope فعلی در دسترس نیست.')
      setApplied(null)
    }
  }, [catalog, filters.model])

  const modelOptions = useMemo(
    () => (catalog?.models || []).map((m) => ({ value: m.key, label: m.label })),
    [catalog],
  )

  const selectedModel = useMemo(
    () => (catalog?.models || []).find((m) => m.key === filters.model),
    [catalog, filters.model],
  )

  const typeFieldOptions = useMemo(() => {
    if (!selectedModel?.type_fields?.length) return []
    return [
      { value: '', label: '— نوع (همه) —' },
      ...selectedModel.type_fields.map((tf) => ({ value: tf.key, label: tf.label })),
    ]
  }, [selectedModel])

  const typeValueOptions = useMemo(() => {
    const tf = selectedModel?.type_fields?.find((t) => t.key === filters.type_field)
    if (!tf?.choices?.length) return [{ value: '', label: 'همه' }]
    return [{ value: '', label: 'همه' }, ...tf.choices.map((c) => ({ value: c.value, label: c.label }))]
  }, [selectedModel, filters.type_field])

  const amountFieldOptions = useMemo(() => {
    if (selectedModel?.amount_fields?.length) {
      return selectedModel.amount_fields.map((f) => ({ value: f.key, label: f.label }))
    }
    if (selectedModel?.amount_label) {
      return [{ value: 'default', label: selectedModel.amount_label }]
    }
    return []
  }, [selectedModel])

  const setModel = (model) => {
    const meta = (catalog?.models || []).find((m) => m.key === model)
    const defaultAmountField = meta?.amount_fields?.[0]?.key
      || (meta?.amount_label ? 'default' : '')
    setFilters({
      ...EMPTY_FILTERS,
      model,
      amount_field: defaultAmountField,
      ...parsedInitialFilters,
    })
    setApplied(null)
  }

  const runFilter = useCallback(async (e) => {
    e?.preventDefault?.()
    const params = buildQueryParams(filters, resultLimit)
    if (!params) {
      setError('مدل را انتخاب کنید.')
      return
    }
    if (onFiltersChange) onFiltersChange(filters, params)
    if (hideResults) {
      setApplied({ total: 0, results: [], hidden: true })
      setError('')
      return
    }
    const seq = ++requestSeq.current
    setLoading(true)
    setError('')
    try {
      const data = await recordFilterApi.query(params)
      if (seq === requestSeq.current) setApplied(data)
    } catch (err) {
      if (seq === requestSeq.current) {
        setError(err.message)
        setApplied(null)
      }
    } finally {
      if (seq === requestSeq.current) setLoading(false)
    }
  }, [filters, hideResults, onFiltersChange, resultLimit])

  const resetFilters = () => {
    setFilters(buildInitialFilters(lockModel, defaultModel, parsedInitialFilters))
    setApplied(null)
    setError('')
  }

  useEffect(() => {
    if (!liveSearch || !filters.model) return undefined
    if (catalog && !catalog.models.some((m) => m.key === filters.model)) return undefined
    const t = setTimeout(() => {
      runFilter()
    }, debounceMs)
    return () => clearTimeout(t)
  }, [filters, liveSearch, debounceMs, runFilter])

  const showAmount = Boolean(selectedModel?.amount_label || selectedModel?.amount_fields?.length)
  const showModelSelect = !lockModel && modelOptions.length !== 1

  return (
    <div className={`record-filter-panel ${compact ? 'record-filter-panel-compact' : ''} ${unified ? 'record-filter-panel-unified' : ''} ${className}`.trim()}>
      {error && <div className="alert-error">{error}</div>}
      {metaLoading ? (
        <p className="muted loading">در حال بارگذاری…</p>
      ) : (
        <form onSubmit={runFilter}>
          <FilterBar>
            {showModelSelect && (
              <Field label="مدل">
                <Select
                  value={filters.model}
                  onChange={setModel}
                  options={[{ value: '', label: 'انتخاب مدل…' }, ...modelOptions]}
                  required
                />
              </Field>
            )}
            {selectedModel?.type_fields?.length > 0 && (
              <>
                <Field label="فیلد نوع">
                  <Select
                    value={filters.type_field}
                    onChange={(v) => setFilters({ ...filters, type_field: v, type: '' })}
                    options={typeFieldOptions}
                  />
                </Field>
                <Field label="نوع">
                  <Select
                    value={filters.type}
                    onChange={(v) => setFilters({ ...filters, type: v })}
                    options={typeValueOptions}
                    disabled={!filters.type_field}
                  />
                </Field>
              </>
            )}
            <Field label={selectedModel?.date_field_label || 'از تاریخ'}>
              <PersianDateInput
                value={filters.date_from}
                onChange={(v) => setFilters({ ...filters, date_from: v })}
                placeholder="از تاریخ"
                onClear={() => setFilters({ ...filters, date_from: '' })}
                clearLabel="پاک"
              />
            </Field>
            <Field label="تا تاریخ">
              <PersianDateInput
                value={filters.date_to}
                onChange={(v) => setFilters({ ...filters, date_to: v })}
                placeholder="تا تاریخ"
                onClear={() => setFilters({ ...filters, date_to: '' })}
                clearLabel="پاک"
              />
            </Field>
            <Field label={selectedModel?.name_label || 'نام / جستجو'}>
              <input
                className="search-input"
                value={filters.name}
                onChange={(e) => setFilters({ ...filters, name: e.target.value })}
                placeholder="جستجوی زنده…"
              />
            </Field>
            {showAmount && amountFieldOptions.length > 1 && (
              <Field label="فیلد مبلغ">
                <Select
                  value={filters.amount_field || amountFieldOptions[0]?.value}
                  onChange={(v) => setFilters({ ...filters, amount_field: v })}
                  options={amountFieldOptions}
                />
              </Field>
            )}
            {showAmount && (
              <>
                <Field label="حداقل مبلغ">
                  <MoneyInput
                    min="0"
                    value={filters.amount_min}
                    onChange={(e) => setFilters({ ...filters, amount_min: e.target.value })}
                  />
                </Field>
                <Field label="حداکثر مبلغ">
                  <MoneyInput
                    min="0"
                    value={filters.amount_max}
                    onChange={(e) => setFilters({ ...filters, amount_max: e.target.value })}
                  />
                </Field>
              </>
            )}
            {!liveSearch && (
              <div className="page-filters-actions">
                <Button type="submit" disabled={loading}>{loading ? 'در حال جستجو…' : 'اعمال فیلتر'}</Button>
                <Button type="button" variant="ghost" onClick={resetFilters}>پاک کردن</Button>
              </div>
            )}
            {liveSearch && (
              <div className="page-filters-actions">
                <Button type="button" variant="ghost" onClick={resetFilters}>پاک کردن فیلترها</Button>
                {loading && <span className="muted small">در حال جستجو…</span>}
              </div>
            )}
          </FilterBar>
        </form>
      )}

      {applied && !hideResults && (
        <div className="record-filter-results">
          <p className="record-filter-count">
            <strong>{toPersianDigits(applied.total)}</strong> رکورد
            {applied.model_label ? ` — ${applied.model_label}` : ''}
            {applied.total > applied.results.length && (
              <> — نمایش {toPersianDigits(applied.results.length)}</>
            )}
            {loading ? ' …' : ''}
          </p>
          {applied.total === 0 ? (
            <EmptyState text="با این فیلتر رکوردی یافت نشد." />
          ) : (
            <>
              <div className="table-wrap record-filter-table-desktop">
                <table className="table">
                  <thead>
                    <tr>
                      <th>شناسه</th>
                      <th>عنوان</th>
                      <th>نوع</th>
                      <th>مبلغ</th>
                      <th>تاریخ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applied.results.map((row) => (
                      <tr key={row.id}>
                        <td>{row.id}</td>
                        <td>
                          <div>{row.title}</div>
                          {row.subtitle && <div className="muted small">{row.subtitle}</div>}
                        </td>
                        <td>{row.type_display || '—'}</td>
                        <td>{row.amount != null ? formatMoney(row.amount) : '—'}</td>
                        <td>{row.date ? formatDate(row.date) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="record-filter-cards-mobile">
                {applied.results.map((row) => (
                  <div key={row.id} className="m-card">
                    <div className="m-card-head">
                      <strong>{row.title}</strong>
                      <span className="muted">#{row.id}</span>
                    </div>
                    {row.subtitle && <p className="muted small">{row.subtitle}</p>}
                    <div className="m-card-grid">
                      <div><span className="muted">نوع</span>{row.type_display || '—'}</div>
                      <div><span className="muted">مبلغ</span>{row.amount != null ? formatMoney(row.amount) : '—'}</div>
                      <div><span className="muted">تاریخ</span>{row.date ? formatDate(row.date) : '—'}</div>
                    </div>
                  </div>
                ))}
              </div>
              <LoadMoreButton
                hasMore={applied.results.length < applied.total}
                loading={loadingMore}
                onClick={async () => {
                  const params = buildQueryParams(filters, resultLimit, applied.results.length)
                  if (!params) return
                  setLoadingMore(true)
                  try {
                    const data = await recordFilterApi.query(params)
                    setApplied((prev) => ({
                      ...data,
                      results: [...(prev?.results || []), ...(data.results || [])],
                    }))
                  } catch (err) {
                    setError(err.message)
                  } finally {
                    setLoadingMore(false)
                  }
                }}
              />
            </>
          )}
        </div>
      )}
      {hideResults && filters.model && loading && (
        <p className="record-filter-count muted small">در حال جستجو…</p>
      )}
    </div>
  )
}
