import { useCallback, useEffect, useMemo, useState } from 'react'
import { materialsApi } from '../api/client'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatDate, formatMoney, formatNumber } from '../utils/format'
import { hasPermission } from '../utils/permissions'
import { fromLegacy, tw } from '../styles/tw.js'

const TYPE_OPTIONS = [
  { value: 'cycle', label: 'دوره‌ای' },
  { value: 'annual', label: 'پایان سال' },
  { value: 'spot', label: 'موردی' },
]

const CONDITION_OPTIONS = [
  { value: 'sound', label: 'سالم' },
  { value: 'damaged', label: 'آسیب‌دیده' },
  { value: 'expired', label: 'تاریخ‌گذشته' },
  { value: 'consignment', label: 'امانی' },
]

const CAUSE_OPTIONS = [
  { value: '', label: 'انتخاب علت' },
  { value: 'entry_error', label: 'خطای ثبت' },
  { value: 'misplacement', label: 'جانمایی اشتباه' },
  { value: 'shrinkage', label: 'مفقودی' },
  { value: 'unrecorded_waste', label: 'ضایعات ثبت‌نشده' },
  { value: 'sync_delay', label: 'تاخیر هماهنگی سیستم' },
]

const cellSelectStyle = { width: '100%', minWidth: 130 }

function digits(value) {
  return String(value ?? '')
    .replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
    .replace(/[,،\s]/g, '')
}

function qty(value, unit) {
  if (value == null || value === '') return '—'
  const text = formatNumber(value)
  return unit ? `${text} ${unit}` : text
}

function percent(part, whole) {
  if (!whole) return null
  return Math.round((part / whole) * 1000) / 10
}

function draftFromSheet(sheet) {
  const next = {}
  for (const row of sheet?.rows || []) {
    next[row.material_id] = {
      physical: row.counted ? String(row.physical_qty) : '',
      condition: row.condition || 'sound',
      root_cause: row.root_cause || '',
    }
  }
  return next
}

function liveVariance(row, edit) {
  if (!edit || edit.physical === '' || edit.physical == null) return null
  const physical = Number(digits(edit.physical))
  if (!Number.isFinite(physical)) return null
  return physical - Number(row.system_qty)
}

function conditionLabel(value) {
  return CONDITION_OPTIONS.find((item) => item.value === value)?.label || 'سالم'
}

function statusOf(variance) {
  if (variance == null) return 'شمارش نشده'
  if (variance < 0) return 'کمتر از سیستم'
  if (variance > 0) return 'بیشتر از سیستم'
  return 'مطابق سیستم'
}

export default function MaterialStocktakeReport() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const canEdit = hasPermission(user, 'create_materials') || hasPermission(user, 'approve_materials')
  const [list, setList] = useState([])
  const [sheet, setSheet] = useState(null)
  const [header, setHeader] = useState({ count_type: 'cycle', scope_note: '', supervisor_name: '', counter_names: '', observer_name: '' })
  const [draft, setDraft] = useState({})
  const [search, setSearch] = useState('')
  const [showZero, setShowZero] = useState(false)
  const [view, setView] = useState('all')
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const applySheet = useCallback((next) => {
    setSheet(next)
    setHeader({
      count_type: next.count_type || 'cycle',
      scope_note: next.scope_note || '',
      supervisor_name: next.supervisor_name || '',
      counter_names: next.counter_names || '',
      observer_name: next.observer_name || '',
    })
    setDraft(draftFromSheet(next))
    setDirty(false)
  }, [])

  const loadList = useCallback(async () => {
    const data = await materialsApi.stocktakes()
    const results = data.results || []
    setList(results)
    return results
  }, [])

  const openSheet = useCallback(async (id) => {
    const data = await materialsApi.stocktake(id)
    applySheet(data)
    setInfo('')
    setError('')
  }, [applySheet])

  useEffect(() => {
    let active = true
    setLoading(true)
    loadList().then(async (results) => {
      if (!active) return
      const preferred = results.find((item) => item.status === 'draft') || results[0]
      if (preferred) await openSheet(preferred.id)
    }).catch((err) => {
      if (active) setError(err.message)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [loadList, openSheet])

  const rows = sheet?.rows || []
  const visibleRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return rows.filter((row) => {
      const edit = draft[row.material_id]
      const counted = edit && edit.physical !== '' && edit.physical != null
      if (!showZero && !counted && Number(row.system_qty) === 0) return false
      const variance = liveVariance(row, edit)
      if (view === 'pending' && variance != null) return false
      if (view === 'gap' && !(variance != null && variance !== 0)) return false
      if (view === 'match' && variance !== 0) return false
      if (!query) return true
      return row.label.toLowerCase().includes(query) || String(row.sku || '').toLowerCase().includes(query)
    })
  }, [rows, draft, search, showZero, view])

  const progress = useMemo(() => {
    let stocked = 0
    let counted = 0
    let pending = 0
    let gap = 0
    let match = 0
    for (const row of rows) {
      const variance = liveVariance(row, draft[row.material_id])
      const hasStock = Number(row.system_qty) > 0 || variance != null
      if (!hasStock) continue
      stocked += 1
      if (variance == null) pending += 1
      else {
        counted += 1
        if (variance === 0) match += 1
        else gap += 1
      }
    }
    return { stocked, counted, pending, gap, match, ratio: stocked ? counted / stocked : 0 }
  }, [rows, draft])

  const hiddenZero = rows.filter((row) => Number(row.system_qty) === 0 && !(draft[row.material_id]?.physical)).length
  const metrics = useMemo(() => {
    let ownedValue = 0
    let shortage = 0
    let overage = 0
    let counted = 0
    let matched = 0
    let countedA = 0
    let matchedA = 0
    const damaged = []
    const consignment = []
    const adjustments = []
    for (const row of rows) {
      const edit = draft[row.material_id] || { physical: '', condition: 'sound', root_cause: '' }
      const variance = liveVariance(row, edit)
      const countedRow = variance != null
      const value = countedRow ? Math.round(variance * Number(row.unit_cost || 0)) : null
      const view = {
        ...row,
        physical_qty: countedRow ? Number(digits(edit.physical)) : null,
        variance_qty: variance,
        variance_value: value,
        condition_label: conditionLabel(edit.condition),
        status_label: statusOf(variance),
      }
      if (edit.condition === 'consignment') {
        if (countedRow) consignment.push(view)
        continue
      }
      ownedValue += Number(row.system_value || 0)
      if (!countedRow) continue
      counted += 1
      if (variance === 0) matched += 1
      if (row.abc_class === 'A') {
        countedA += 1
        if (variance === 0) matchedA += 1
      }
      if (value < 0) shortage += -value
      else if (value > 0) overage += value
      if (variance !== 0) adjustments.push(view)
      if (edit.condition === 'damaged' || edit.condition === 'expired') damaged.push(view)
    }
    return {
      accuracy: percent(matched, counted),
      classA: percent(matchedA, countedA),
      shrinkage: counted ? percent(shortage, ownedValue) : null,
      shortage,
      overage,
      counted,
      damaged,
      consignment,
      adjustments,
    }
  }, [rows, draft])

  const editable = Boolean(sheet?.editable && canEdit)

  const markDirty = () => {
    setDirty(true)
    setInfo('')
  }

  const setLine = (materialId, patch) => {
    markDirty()
    setDraft((prev) => ({
      ...prev,
      [materialId]: { ...(prev[materialId] || { physical: '', condition: 'sound', root_cause: '' }), ...patch },
    }))
  }

  const discardIfDirty = async () => {
    if (!dirty) return true
    return confirm({
      title: 'تغییرهای ذخیره نشده',
      message: 'شمارش‌هایی که ذخیره نشده از این برگه برداشته شود؟',
      confirmText: 'ادامه بدون ذخیره',
    })
  }

  const payload = () => ({
    ...header,
    lines: rows.map((row) => {
      const edit = draft[row.material_id] || {}
      const physical = digits(edit.physical)
      return {
        material_id: row.material_id,
        physical_qty: physical === '' ? '' : physical,
        condition: edit.condition || 'sound',
        root_cause: edit.root_cause || '',
      }
    }),
  })

  const startSheet = async () => {
    if (!await discardIfDirty()) return
    setSaving(true)
    try {
      const created = await materialsApi.createStocktake({ count_type: header.count_type || 'cycle' })
      applySheet(created)
      await loadList()
      setInfo('برگه تازه ساخته شد. تعداد شمارش‌شده را در ستون «شمارش انبار» بنویسید.')
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const changeSheet = async (id) => {
    if (!id || String(id) === String(sheet?.id)) return
    if (!await discardIfDirty()) return
    try {
      await openSheet(id)
    } catch (err) {
      setError(err.message)
    }
  }

  const saveSheet = async () => {
    setSaving(true)
    try {
      const saved = await materialsApi.saveStocktake(sheet.id, payload())
      applySheet(saved)
      await loadList()
      setInfo('پیش‌نویس ذخیره شد. موجودی انبار عوض نشده است.')
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const closeSheet = async () => {
    if (!await confirm({
      title: 'بستن برگه انبارگردانی',
      message: 'بعد از بستن، شمارش این برگه قفل می‌شود. موجودی انبار همان عدد سیستم می‌ماند.',
      confirmText: 'بستن برگه',
    })) return
    setSaving(true)
    try {
      await materialsApi.saveStocktake(sheet.id, payload())
      const closed = await materialsApi.closeStocktake(sheet.id)
      applySheet(closed)
      await loadList()
      setInfo('برگه بسته شد. موجودی انبار تغییر نکرد.')
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const focusNext = () => {
    const pool = view === 'gap' || view === 'match' ? rows : visibleRows
    const target = pool.find((row) => liveVariance(row, draft[row.material_id]) == null && (Number(row.system_qty) > 0 || showZero))
    if (!target) return
    if (view !== 'all' && view !== 'pending') setView('pending')
    requestAnimationFrame(() => {
      document.getElementById(`stock-count-${target.material_id}`)?.focus()
    })
  }

  if (loading) return <div className={fromLegacy('loading')}>در حال بارگذاری…</div>

  return (
    <div>
      <p className={fromLegacy('muted')} style={{ marginTop: 0 }}>
        عدد سیستم را با شمارشی که در انبار انجام شده مقایسه کنید. ذخیره و بستن برگه موجودی انبار را عوض نمی‌کند.
      </p>
      {error && <div className={fromLegacy('alert-error')}>{error}</div>}
      {info && <div className={fromLegacy('alert-success')}>{info}</div>}

      <Card>
        <div className={fromLegacy('form-grid-2')}>
          <Field label="برگه">
            <Select
              value={sheet ? String(sheet.id) : ''}
              onChange={changeSheet}
              options={list.map((item) => ({
                value: String(item.id),
                label: `${item.count_type_display} · ${item.status_display} · ${formatDate(item.started_at)}`,
              }))}
              placeholder="هنوز برگه‌ای نیست"
            />
          </Field>
          <Field label="کار با برگه">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {canEdit && <Button type="button" onClick={startSheet} disabled={saving}>برگه جدید</Button>}
              {editable && <Button type="button" onClick={saveSheet} disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره'}</Button>}
              {editable && <Button type="button" variant="ghost" onClick={closeSheet} disabled={saving}>بستن برگه</Button>}
            </div>
          </Field>
        </div>
      </Card>

      {!sheet ? (
        <EmptyState text="با «برگه جدید» یک شمارش بسازید، بعد تعداد هر متریال را در جدول بنویسید." />
      ) : (
        <>
          <Card
            title={sheet.status === 'closed' ? 'شناسنامه برگه بسته' : 'شناسنامه این شمارش'}
            actions={(
              <Button type="button" variant="ghost" size="sm" onClick={() => setDetailsOpen((open) => !open)}>
                {detailsOpen ? 'بستن مشخصات' : 'مشخصات برگه'}
              </Button>
            )}
          >
            <p className={fromLegacy('muted small')}>
              {sheet.count_type_display}
              {' · '}
              {header.scope_note || 'محدوده ثبت نشده'}
              {header.supervisor_name ? ` · سرپرست ${header.supervisor_name}` : ''}
              {' · شروع '}
              {formatDate(sheet.started_at)}
              {sheet.finished_at ? ` · پایان ${formatDate(sheet.finished_at)}` : ''}
              {dirty ? ' · ذخیره نشده' : ''}
            </p>
            {detailsOpen && (
              <div className={fromLegacy('form-grid-2')}>
                <Field label="نوع شمارش">
                  <Select
                    value={header.count_type}
                    onChange={(value) => { markDirty(); setHeader({ ...header, count_type: value }) }}
                    options={TYPE_OPTIONS}
                    disabled={!editable}
                  />
                </Field>
                <Field label="کجای انبار شمرده شد">
                  <input value={header.scope_note} disabled={!editable} placeholder="مثلاً قفسه پارچه" onChange={(e) => { markDirty(); setHeader({ ...header, scope_note: e.target.value }) }} />
                </Field>
                <Field label="سرپرست شمارش">
                  <input value={header.supervisor_name} disabled={!editable} onChange={(e) => { markDirty(); setHeader({ ...header, supervisor_name: e.target.value }) }} />
                </Field>
                <Field label="کسانی که شمردند">
                  <input value={header.counter_names} disabled={!editable} placeholder="نام شمارش‌گرها" onChange={(e) => { markDirty(); setHeader({ ...header, counter_names: e.target.value }) }} />
                </Field>
                <Field label="ناظر">
                  <input value={header.observer_name} disabled={!editable} onChange={(e) => { markDirty(); setHeader({ ...header, observer_name: e.target.value }) }} />
                </Field>
              </div>
            )}
          </Card>

          <div className={fromLegacy('stat-grid')}>
            <StatCard label="پیشرفت شمارش" value={`${formatNumber(progress.counted)} از ${formatNumber(progress.stocked)}`} hint="قلم‌های دارای موجودی" />
            <StatCard label="دقت شمارش" value={metrics.accuracy == null ? '—' : `${formatNumber(metrics.accuracy)}٪`} hint="سهم قلم‌هایی که با سیستم یکی بودند" onClick={() => setView('match')} active={view === 'match'} />
            <StatCard label="اختلاف" value={formatNumber(progress.gap)} hint="کمتر یا بیشتر از سیستم" accent="var(--warning)" onClick={() => setView('gap')} active={view === 'gap'} />
            <StatCard label="مانده" value={formatNumber(progress.pending)} hint="هنوز شمارش نشده" onClick={() => setView('pending')} active={view === 'pending'} />
            <StatCard label="مبلغ کمبود" value={formatMoney(metrics.shortage)} accent="var(--danger)" />
          </div>
          <div className={tw.barTrack} style={{ margin: '4px 0 12px' }}>
            <div className={tw.barFill} style={{ width: `${Math.round(progress.ratio * 100)}%`, background: 'var(--accent)' }} />
          </div>

          <Card
            title="جدول شمارش"
            actions={editable ? <Button type="button" variant="ghost" size="sm" onClick={focusNext}>شمارش بعدی</Button> : null}
          >
            <div className={fromLegacy('workflow-filter-tabs')} style={{ marginBottom: 12 }}>
              {[
                { id: 'all', label: 'همه' },
                { id: 'pending', label: `مانده ${formatNumber(progress.pending)}` },
                { id: 'gap', label: `اختلاف ${formatNumber(progress.gap)}` },
                { id: 'match', label: `مطابق ${formatNumber(progress.match)}` },
              ].map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={fromLegacy(`workflow-filter-tab ${view === item.id ? 'active' : ''}`)}
                  onClick={() => setView(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <div className={fromLegacy('form-grid-2')}>
              <Field label="جستجو">
                <input className={fromLegacy('search-input')} value={search} onChange={(e) => setSearch(e.target.value)} placeholder="نام یا کد متریال" />
              </Field>
              <Field label="نمایش">
                <label className={fromLegacy('checkbox-row')}>
                  <input type="checkbox" checked={showZero} onChange={(e) => setShowZero(e.target.checked)} />
                  قلم‌های بدون موجودی
                  {hiddenZero > 0 ? ` (${formatNumber(hiddenZero)})` : ''}
                </label>
              </Field>
            </div>
            {visibleRows.length === 0 ? (
              <EmptyState text="متریالی برای این جستجو نیست." />
            ) : (
              <div className={fromLegacy('table-wrap')}>
                <table className={fromLegacy('table')}>
                  <thead>
                    <tr>
                      <th>متریال</th>
                      <th>موجودی سیستم</th>
                      <th>شمارش انبار</th>
                      <th>اختلاف</th>
                      <th>مبلغ اختلاف</th>
                      <th>نتیجه</th>
                      <th>وضعیت کالا</th>
                      <th>چرا فرق دارد</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((row) => {
                      const edit = draft[row.material_id] || { physical: '', condition: 'sound', root_cause: '' }
                      const variance = liveVariance(row, edit)
                      const varianceValue = variance == null ? null : Math.round(variance * Number(row.unit_cost || 0))
                      const hasGap = variance != null && variance !== 0
                      const tone = variance == null ? undefined : variance < 0 ? 'var(--danger)' : variance > 0 ? 'var(--warning)' : 'var(--success)'
                      return (
                        <tr key={row.material_id} style={tone ? { boxShadow: `inset 3px 0 0 ${tone}` } : undefined}>
                          <td>
                            <strong>{row.label}</strong>
                            <div className={fromLegacy('muted small')}>
                              {row.abc_class ? `کلاس ${row.abc_class}` : 'بدون کلاس'}
                              {row.sku ? ` · ${row.sku}` : ''}
                            </div>
                          </td>
                          <td>{qty(row.system_qty, row.unit)}</td>
                          <td>
                            <input
                              id={`stock-count-${row.material_id}`}
                              className={fromLegacy('ltr')}
                              type="number"
                              min="0"
                              step="0.001"
                              style={{ width: 120, fontSize: 16, textAlign: 'center' }}
                              value={edit.physical}
                              disabled={!editable}
                              placeholder="تعداد"
                              onChange={(e) => setLine(row.material_id, { physical: e.target.value, root_cause: e.target.value === '' ? '' : edit.root_cause })}
                              onKeyDown={(e) => {
                                if (e.key !== 'Enter') return
                                e.preventDefault()
                                const index = visibleRows.findIndex((item) => item.material_id === row.material_id)
                                const following = visibleRows[index + 1]
                                if (following) document.getElementById(`stock-count-${following.material_id}`)?.focus()
                              }}
                            />
                          </td>
                          <td style={tone ? { color: tone, fontWeight: 700 } : undefined}>
                            {variance == null ? '—' : qty(variance, row.unit)}
                          </td>
                          <td>{varianceValue == null ? '—' : formatMoney(varianceValue)}</td>
                          <td><Badge color={tone || 'var(--muted)'}>{statusOf(variance)}</Badge></td>
                          <td>
                            <select
                              style={cellSelectStyle}
                              value={edit.condition}
                              disabled={!editable}
                              onChange={(e) => setLine(row.material_id, { condition: e.target.value })}
                            >
                              {CONDITION_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                            </select>
                          </td>
                          <td>
                            <select
                              style={cellSelectStyle}
                              value={hasGap ? edit.root_cause : ''}
                              disabled={!editable || !hasGap}
                              onChange={(e) => setLine(row.material_id, { root_cause: e.target.value })}
                            >
                              {CAUSE_OPTIONS.map((item) => <option key={item.value || 'none'} value={item.value}>{item.label}</option>)}
                            </select>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {dirty && editable && (
            <div
              style={{
                position: 'sticky',
                bottom: 88,
                zIndex: 5,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                padding: '12px 16px',
                borderRadius: 16,
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                boxShadow: 'var(--shadow)',
              }}
            >
              <span>شمارش هنوز ذخیره نشده</span>
              <Button type="button" onClick={saveSheet} disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره'}</Button>
            </div>
          )}

          {metrics.damaged.length > 0 && (
            <Card title="کالای آسیب‌دیده یا تاریخ‌گذشته">
              <SimpleTable rows={metrics.damaged} />
            </Card>
          )}
          {metrics.consignment.length > 0 && (
            <Card title="کالای امانی">
              <p className={fromLegacy('muted small')}>این ردیف‌ها در دقت شمارش و سهم کمبود حساب نمی‌شوند.</p>
              <SimpleTable rows={metrics.consignment} />
            </Card>
          )}
          {(sheet.dead_stock || []).length > 0 && (
            <Card title={`راکد: ${formatNumber(sheet.dead_stock_days)} روز خروجی نداشته`}>
              <p className={fromLegacy('muted small')}>این کالاها فضا و پول انبار را گرفته‌اند. جایشان را به نقطه خلوت‌تر ببرید.</p>
              <div className={fromLegacy('table-wrap')}>
                <table className={fromLegacy('table')}>
                  <thead><tr><th>متریال</th><th>موجودی</th><th>ارزش</th></tr></thead>
                  <tbody>
                    {sheet.dead_stock.map((row) => (
                      <tr key={row.material_id}>
                        <td>{row.label}</td>
                        <td>{qty(row.on_hand, row.unit)}</td>
                        <td>{formatMoney(row.inventory_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
          <Card title="پیشنهاد اصلاح">
            <p className={fromLegacy('muted small')}>این فهرست فقط برای تصمیم مدیریت است و موجودی را کم یا زیاد نمی‌کند.</p>
            {metrics.adjustments.length === 0 ? (
              <EmptyState text="اختلافی برای اصلاح نیست." />
            ) : (
              <SimpleTable rows={metrics.adjustments} />
            )}
            <p className={fromLegacy('muted small')}>شمارش بعدی: کلاس A هر ماه، کلاس B هر فصل، کلاس C هر سال.</p>
            <ul>
              {(sheet.suggestions || []).filter((note) => note.includes('دقت') || note.includes('راکد')).map((note) => <li key={note}>{note}</li>)}
            </ul>
          </Card>
        </>
      )}
    </div>
  )
}

function SimpleTable({ rows }) {
  return (
    <div className={fromLegacy('table-wrap')}>
      <table className={fromLegacy('table')}>
        <thead>
          <tr>
            <th>متریال</th>
            <th>موجودی سیستم</th>
            <th>شمارش انبار</th>
            <th>اختلاف</th>
            <th>مبلغ اختلاف</th>
            <th>نتیجه</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.material_id}-${row.condition_label}`}>
              <td>{row.label}</td>
              <td>{qty(row.system_qty, row.unit)}</td>
              <td>{qty(row.physical_qty, row.unit)}</td>
              <td>{qty(row.variance_qty, row.unit)}</td>
              <td>{formatMoney(row.variance_value)}</td>
              <td>{row.status_label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
