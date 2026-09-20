import { useCallback, useEffect, useMemo, useState } from 'react'
import { furnitureWorksetsApi } from '../api/client'
import Icon from '../components/icons/Icon'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton } from '../components/ui'
import { PAGE_SIZE } from '../config/pagination'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { hasPermission } from '../utils/permissions'
import { toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_WORKSET = { name: '', design_style: '', seat_count: '', is_active: true, qtys: {} }

const SEAT_COUNT = {
  armchair: 1,
  sofa_2: 2,
  sofa_3: 3,
  sofa_4: 4,
  sofa_5: 5,
  chaise: 2,
  pouf: 1,
  bench: 3,
  loveseat: 2,
  side_table: 0,
  coffee_table: 0,
}

function slotKey(kind, arm) {
  return `${kind}:${arm}`
}

function groupSlots(slots) {
  const groups = []
  const map = new Map()
  for (const slot of slots) {
    if (!map.has(slot.piece_kind)) {
      const group = { piece_kind: slot.piece_kind, group: slot.group, slots: [] }
      map.set(slot.piece_kind, group)
      groups.push(group)
    }
    map.get(slot.piece_kind).slots.push(slot)
  }
  return groups
}

function qtysFromPieces(pieces = []) {
  const qtys = {}
  pieces.forEach((piece) => {
    qtys[slotKey(piece.piece_kind, piece.arm_style)] = String(piece.quantity || 0)
  })
  return qtys
}

function piecesFromQtys(qtys, slots) {
  return slots
    .map((slot) => ({
      piece_kind: slot.piece_kind,
      arm_style: slot.arm_style,
      quantity: Number(qtys[slotKey(slot.piece_kind, slot.arm_style)] || 0),
    }))
    .filter((piece) => piece.quantity > 0)
}

function armOptionsFor(group) {
  return (group?.slots || []).map((slot) => ({
    value: slot.arm_style,
    label: slot.show_arm ? slot.arm_label : group.group,
  }))
}

function PieceGlyph({ kind, arm }) {
  const seats = SEAT_COUNT[kind] ?? 1
  const isTable = kind === 'side_table' || kind === 'coffee_table'
  const isPouf = kind === 'pouf'
  const isChaise = kind === 'chaise'
  const isBench = kind === 'bench'
  const left = arm === 'two' || arm === 'one_left' || arm === 'one'
  const right = arm === 'two' || arm === 'one_right'
  const wide = kind === 'coffee_table'

  return (
    <svg className="piece-glyph-svg" viewBox="0 0 80 42" aria-hidden>
      {isTable ? (
        <>
          <rect x={wide ? 10 : 20} y="12" width={wide ? 60 : 40} height="8" rx="2" />
          <rect x={wide ? 16 : 26} y="20" width="4" height="12" rx="1" />
          <rect x={wide ? 60 : 50} y="20" width="4" height="12" rx="1" />
        </>
      ) : isPouf ? (
        <rect x="26" y="10" width="28" height="22" rx="10" />
      ) : (
        <>
          {left && <rect x="4" y="8" width="7" height="24" rx="2.5" />}
          {Array.from({ length: Math.max(seats, 1) }).map((_, index) => {
            const gap = 2
            const inner = 58
            const w = (inner - gap * (seats - 1)) / seats
            const x = 11 + index * (w + gap)
            const h = isBench ? 12 : isChaise && index === seats - 1 ? 20 : 16
            const y = isBench ? 16 : isChaise && index === seats - 1 ? 10 : 12
            return <rect key={index} x={x} y={y} width={w} height={h} rx="3" />
          })}
          {right && <rect x="69" y="8" width="7" height="24" rx="2.5" />}
        </>
      )}
    </svg>
  )
}

function QtyStepper({ value, onChange, min = 0 }) {
  const qty = Number(value || 0)
  return (
    <div className="piece-qty">
      <button type="button" onClick={() => onChange(qty - 1)} disabled={qty <= min} aria-label="کم">
        <Icon name="minus" size={14} />
      </button>
      <input
        className={fromLegacy('ltr')}
        type="number"
        min={min}
        max="99"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder="0"
      />
      <button type="button" onClick={() => onChange(qty + 1)} aria-label="زیاد">
        <Icon name="plus" size={14} />
      </button>
    </div>
  )
}

export default function Frames() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const canManage = hasPermission(user, 'manage_frames')
  useRegisterPageGuide('factory-frames', PAGE_GUIDE_DEFAULTS['factory-frames'])

  const [worksets, setWorksets] = useState([])
  const [options, setOptions] = useState({ piece_slots: [], design_styles: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [catalogSearch, setCatalogSearch] = useState('')
  const [activeArm, setActiveArm] = useState({})
  const [formOpen, setFormOpen] = useState(false)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)
  const [editingWorkset, setEditingWorkset] = useState(null)
  const [worksetForm, setWorksetForm] = useState(EMPTY_WORKSET)
  const [saving, setSaving] = useState(false)

  const slots = options.piece_slots || []
  const groupedSlots = useMemo(() => groupSlots(slots), [slots])
  const selectedPieces = useMemo(() => piecesFromQtys(worksetForm.qtys, slots), [worksetForm.qtys, slots])
  const selectedCount = selectedPieces.reduce((sum, piece) => sum + piece.quantity, 0)

  useEffect(() => {
    setActiveArm((prev) => {
      const next = { ...prev }
      groupedSlots.forEach((group) => {
        if (!next[group.piece_kind]) next[group.piece_kind] = group.slots[0]?.arm_style || ''
      })
      return next
    })
  }, [groupedSlots])

  const visibleGroups = useMemo(() => {
    const q = catalogSearch.trim()
    return groupedSlots.filter((group) => {
      if (!q) return true
      return `${group.group} ${group.slots.map((slot) => slot.arm_label || '').join(' ')}`.includes(q)
    })
  }, [groupedSlots, catalogSearch])

  const loadWorksets = useCallback(async (reset = false) => {
    setLoading(true)
    setError('')
    try {
      const nextOffset = reset ? 0 : offset + PAGE_SIZE
      const data = await furnitureWorksetsApi.list({
        search: search.trim(),
        offset: nextOffset,
        limit: PAGE_SIZE,
        include_inactive: canManage,
      })
      const results = data.results || []
      setWorksets(reset ? results : (prev) => [...prev, ...results])
      setOffset(nextOffset)
      setTotal(data.total || 0)
    } catch (err) {
      setError(err.message || 'خطا در بارگذاری دست‌ها')
    } finally {
      setLoading(false)
    }
  }, [search, offset, canManage])

  useEffect(() => {
    furnitureWorksetsApi.options().then(setOptions).catch(() => {})
  }, [])

  useEffect(() => { loadWorksets(true) }, [search])

  const resetComposer = () => {
    setEditingWorkset(null)
    setWorksetForm({ ...EMPTY_WORKSET, qtys: {} })
    setCatalogSearch('')
    setFormOpen(false)
  }

  const openCreate = () => {
    setEditingWorkset(null)
    setWorksetForm({ ...EMPTY_WORKSET, qtys: {} })
    setCatalogSearch('')
    setError('')
    setFormOpen(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const openEdit = (workset) => {
    setEditingWorkset(workset)
    const qtys = qtysFromPieces(workset.pieces)
    setWorksetForm({
      name: workset.name || '',
      design_style: workset.design_style || '',
      seat_count: workset.seat_count ? String(workset.seat_count) : '',
      is_active: workset.is_active !== false,
      qtys,
    })
    const arms = {}
    ;(workset.pieces || []).forEach((piece) => {
      if (!arms[piece.piece_kind]) arms[piece.piece_kind] = piece.arm_style
    })
    setActiveArm((prev) => ({ ...prev, ...arms }))
    setCatalogSearch('')
    setError('')
    setFormOpen(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const setQty = (kind, arm, value) => {
    const next = Math.max(0, Math.min(99, Number(value) || 0))
    const key = slotKey(kind, arm)
    setWorksetForm((form) => ({
      ...form,
      qtys: { ...form.qtys, [key]: next ? String(next) : '' },
    }))
  }

  const saveWorkset = async (e) => {
    e.preventDefault()
    if (!selectedPieces.length) {
      setError('از کاتالوگ حداقل یک قطعه انتخاب کنید.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = {
        name: worksetForm.name.trim(),
        design_style: worksetForm.design_style,
        seat_count: worksetForm.seat_count ? Number(worksetForm.seat_count) : null,
        is_active: worksetForm.is_active,
        pieces: selectedPieces,
      }
      if (editingWorkset?.id) await furnitureWorksetsApi.update(editingWorkset.id, payload)
      else await furnitureWorksetsApi.create(payload)
      resetComposer()
      await loadWorksets(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeWorkset = async (workset) => {
    if (!canManage) return
    const ok = await confirm(`دست «${workset.name}» حذف شود؟`)
    if (!ok) return
    try {
      await furnitureWorksetsApi.remove(workset.id)
      if (editingWorkset?.id === workset.id) resetComposer()
      loadWorksets(true)
    } catch (err) {
      setError(err.message)
    }
  }

  const formTitle = editingWorkset ? `ویرایش دست «${editingWorkset.name}»` : 'ثبت دست'

  return (
    <div className={fromLegacy('page frames-page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1 className={fromLegacy('page-title')}>تولید کلاف</h1>
          <p className={fromLegacy('muted')}>دست را ثبت کنید و قطعات را از کاتالوگ داخل فرم انتخاب کنید.</p>
        </div>
        {canManage && (
          <Button type="button" onClick={openCreate}>ثبت دست</Button>
        )}
      </div>

      {error && <div className={fromLegacy('alert-error')}>{error}</div>}

      {canManage && formOpen && (
        <Card title={formTitle} className="workset-register-card">
          <form onSubmit={saveWorkset} className={fromLegacy('form')}>
            <div className={fromLegacy('form-grid-2')}>
              <Field label="نام دست">
                <input
                  value={worksetForm.name}
                  onChange={(e) => setWorksetForm({ ...worksetForm, name: e.target.value })}
                  required
                  placeholder="مثلاً لونا"
                />
              </Field>
              <Field label="تعداد نفر (دستی)">
                <input
                  className={fromLegacy('ltr')}
                  type="number"
                  min="1"
                  value={worksetForm.seat_count}
                  onChange={(e) => setWorksetForm({ ...worksetForm, seat_count: e.target.value })}
                  placeholder="مثلاً ۸"
                />
              </Field>
              <Field label="سبک طراحی">
                <Select
                  value={worksetForm.design_style}
                  onChange={(v) => setWorksetForm({ ...worksetForm, design_style: v })}
                  options={[{ value: '', label: '—' }, ...(options.design_styles || [])]}
                />
              </Field>
              <label className={fromLegacy('checkbox-row')}>
                <input type="checkbox" checked={worksetForm.is_active} onChange={(e) => setWorksetForm({ ...worksetForm, is_active: e.target.checked })} />
                فعال
              </label>
            </div>

            <div className="piece-form-section">
              <div className={fromLegacy('section-head')}>
                <div>
                  <h4>کاتالوگ قطعات</h4>
                  <p className={fromLegacy('muted small')}>نوع را انتخاب کنید، حالت دسته را از دراپ‌داون بگذارید و تعداد بدهید.</p>
                </div>
                {selectedCount > 0 && <Badge>{toPersianDigits(selectedCount)} قطعه</Badge>}
              </div>

              {selectedPieces.length > 0 && (
                <div className="piece-selected-tray">
                  {selectedPieces.map((piece) => {
                    const slot = slots.find((row) => row.piece_kind === piece.piece_kind && row.arm_style === piece.arm_style)
                    return (
                      <span key={slotKey(piece.piece_kind, piece.arm_style)} className="piece-chip">
                        {toPersianDigits(piece.quantity)}× {slot?.label || piece.piece_kind}
                        <button type="button" onClick={() => setQty(piece.piece_kind, piece.arm_style, 0)} aria-label="حذف">
                          <Icon name="x" size={12} />
                        </button>
                      </span>
                    )
                  })}
                </div>
              )}

              <Field label="جستجوی قطعه">
                <input
                  className={fromLegacy('search-input')}
                  value={catalogSearch}
                  onChange={(e) => setCatalogSearch(e.target.value)}
                  placeholder="مبل تک، کاناپه، شزلون…"
                />
              </Field>

              {visibleGroups.length === 0 ? (
                <EmptyState text="قطعه‌ای یافت نشد." />
              ) : (
                <div className="piece-catalog-grid in-form">
                  {visibleGroups.map((group) => {
                    const arm = activeArm[group.piece_kind] || group.slots[0]?.arm_style
                    const arms = armOptionsFor(group)
                    const qty = Number(worksetForm.qtys[slotKey(group.piece_kind, arm)] || 0)
                    const kindTotal = selectedPieces
                      .filter((piece) => piece.piece_kind === group.piece_kind)
                      .reduce((sum, piece) => sum + piece.quantity, 0)
                    return (
                      <article key={group.piece_kind} className={`piece-card${kindTotal > 0 ? ' selected' : ''}`}>
                        <div className="piece-card-main static">
                          <span className="piece-glyph">
                            <PieceGlyph kind={group.piece_kind} arm={arm} />
                          </span>
                          <strong>{group.group}</strong>
                        </div>
                        {arms.length > 1 && (
                          <Field label="حالت دسته">
                            <Select
                              value={arm}
                              onChange={(value) => setActiveArm((prev) => ({ ...prev, [group.piece_kind]: value }))}
                              options={arms}
                              label="حالت دسته"
                            />
                          </Field>
                        )}
                        <Field label="تعداد">
                          <QtyStepper
                            value={qty ? String(qty) : ''}
                            onChange={(value) => setQty(group.piece_kind, arm, value)}
                          />
                        </Field>
                      </article>
                    )
                  })}
                </div>
              )}
            </div>

            <div className={fromLegacy('form-actions')}>
              <Button type="button" variant="ghost" onClick={resetComposer} disabled={saving}>انصراف</Button>
              <Button type="submit" disabled={saving || !selectedPieces.length}>
                {saving ? 'در حال ذخیره…' : editingWorkset ? 'ذخیره تغییرات' : 'ثبت دست'}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Card title="دست‌های ثبت‌شده">
        <FilterBar>
          <Field label="جستجوی دست">
            <input
              className={fromLegacy('search-input')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="نام دست…"
            />
          </Field>
        </FilterBar>
        {loading && worksets.length === 0 ? (
          <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
        ) : worksets.length === 0 ? (
          <EmptyState text="دستی ثبت نشده. با «ثبت دست» از کاتالوگ قطعه انتخاب کنید." />
        ) : (
          <div className="workset-catalog-grid">
            {worksets.map((workset) => (
              <article
                key={workset.id}
                className={`workset-card${editingWorkset?.id === workset.id ? ' selected' : ''}${workset.is_active ? '' : ' inactive'}`}
              >
                <button type="button" className="workset-card-main" onClick={() => canManage && openEdit(workset)}>
                  <div className="workset-card-head">
                    <h3>{workset.name}</h3>
                    {!workset.is_active && <Badge>غیرفعال</Badge>}
                  </div>
                  <div className={fromLegacy('muted small')}>
                    {toPersianDigits(workset.piece_count || 0)} قطعه
                    {workset.seat_count ? ` • ${toPersianDigits(workset.seat_count)} نفر` : ''}
                    {workset.design_style ? ` • ${options.design_styles?.find((row) => row.value === workset.design_style)?.label || workset.design_style}` : ''}
                  </div>
                  <div className="piece-selected-tray compact">
                    {(workset.pieces || []).map((piece) => (
                      <span key={`${piece.piece_kind}:${piece.arm_style}`} className="piece-chip quiet">
                        {toPersianDigits(piece.quantity)}× {piece.piece_label}
                      </span>
                    ))}
                  </div>
                </button>
                {canManage && (
                  <div className="workset-card-actions">
                    <button type="button" className={fromLegacy('link')} onClick={() => openEdit(workset)}>ویرایش</button>
                    <button type="button" className={fromLegacy('link danger')} onClick={() => removeWorkset(workset)}>حذف</button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
        <LoadMoreButton hasMore={worksets.length < total} loading={loading} onClick={() => loadWorksets(false)} />
      </Card>
    </div>
  )
}
