import { useCallback, useEffect, useMemo, useState } from 'react'
import { fromLegacy } from '../styles/tw.js'

import { materialsApi } from '../api/client'

import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'

import UnitSelect, { resolveUnitValue, splitUnitValue } from '../components/UnitSelect'

import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { PAGE_SIZE } from '../config/pagination'

import { useAuth } from '../context/AuthContext'

import { useConfirm } from '../context/ConfirmContext'

import { formatMoney } from '../utils/format'

import { parseRoute } from '../utils/routing'

import { hasPermission } from '../utils/permissions'

import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'

import { useRegisterPageGuide } from '../context/PageGuideContext'



const COLOR_PRESETS = [

  { name: 'قرمز', hex: 'var(--danger)' },

  { name: 'نارنجی', hex: '#f97316' },

  { name: 'زرد', hex: '#eab308' },

  { name: 'سبز', hex: '#22c55e' },

  { name: 'آبی', hex: '#3b82f6' },

  { name: 'بنفش', hex: '#8b5cf6' },

  { name: 'مشکی', hex: '#1f2937' },

  { name: 'سفید', hex: '#f8fafc' },

  { name: 'خاکستری', hex: '#78716c' },

  { name: 'آبی آسمانی', hex: '#0284c7' },

]



const APPROVAL_COLORS = {

  pending: 'var(--warning)',

  approved: 'var(--success)',

  rejected: 'var(--danger)',

}



const USAGE_KIND_OPTIONS = [
  { value: 'wood', label: 'چوب' },
  { value: 'paint', label: 'رنگ' },
  { value: 'fabric', label: 'پارچه' },
  { value: 'foam', label: 'اسفنج' },
  { value: 'webbing', label: 'تسمه' },
  { value: 'cushion', label: 'کوسن' },
  { value: 'other', label: 'سایر' },
]

const EMPTY_MATERIAL = {

  name: '',

  usage_kind: 'other',

  color_name: '',

  color_hex: '#cccccc',

  sku: '',

  unit_preset: 'متر',

  unit_custom: '',

  unit_cost: '',

  stock: '',

  description: '',

  is_active: true,

}



export default function Materials() {

  const { user } = useAuth()

  const confirm = useConfirm()

  const { portal } = parseRoute()

  const isOffice = portal === 'office'

  const canCreate = hasPermission(user, 'create_materials') || hasPermission(user, 'approve_materials')

  const canApprove = hasPermission(user, 'approve_materials')

  useRegisterPageGuide(
    'materials',
    isOffice ? PAGE_GUIDE_DEFAULTS.materials_office : PAGE_GUIDE_DEFAULTS.materials_shop,
  )

  const [materials, setMaterials] = useState([])

  const [loading, setLoading] = useState(true)

  const [error, setError] = useState('')

  const [search, setSearch] = useState('')

  const [statusFilter, setStatusFilter] = useState(isOffice ? 'pending' : 'all')

  const [total, setTotal] = useState(0)

  const [offset, setOffset] = useState(0)

  const [loadingMore, setLoadingMore] = useState(false)

  const [modal, setModal] = useState(false)

  const [directApprove, setDirectApprove] = useState(false)

  const [editing, setEditing] = useState(null)

  const [form, setForm] = useState(EMPTY_MATERIAL)

  const [saving, setSaving] = useState(false)

  const previewInventoryValue = useMemo(() => {
    const stock = form.stock === '' ? null : Number(form.stock)
    const unitCost = Number(form.unit_cost) || 0
    if (stock == null || Number.isNaN(stock)) return null
    return Math.round(stock * unitCost)
  }, [form.stock, form.unit_cost])

  const load = useCallback(async ({ append = false, offset: nextOffset = 0 } = {}) => {

    if (append) setLoadingMore(true)

    else setLoading(true)

    try {

      const data = await materialsApi.list({

        search: search.trim(),

        offset: nextOffset,

        limit: PAGE_SIZE,

        include_pending: !isOffice || statusFilter !== 'approved',

        approval_status: isOffice && statusFilter !== 'all' ? statusFilter : undefined,

        include_inactive: canApprove,

      })

      setMaterials((prev) => (append ? [...prev, ...(data.results || [])] : (data.results || [])))

      setTotal(data.total || 0)

      setOffset(data.offset ?? nextOffset)

      setError('')

    } catch (e) {

      setError(e.message)

    } finally {

      setLoading(false)

      setLoadingMore(false)

    }

  }, [search, isOffice, statusFilter, canApprove])



  useEffect(() => { load() }, [load])



  const openCreate = (autoApprove = false) => {

    setEditing(null)

    setDirectApprove(autoApprove)

    setForm(EMPTY_MATERIAL)

    setModal(true)

  }



  const openEdit = (m) => {

    const { preset, custom } = splitUnitValue(m.unit)

    setEditing(m)

    setForm({

      name: m.name,

      usage_kind: m.usage_kind || 'other',

      color_name: m.color_name || '',

      color_hex: m.color_hex || '#cccccc',

      sku: m.sku || '',

      unit_preset: preset,

      unit_custom: custom,

      unit_cost: String(m.unit_cost ?? ''),

      stock: m.stock != null ? String(m.stock) : '',

      description: m.description || '',

      is_active: m.is_active !== false,

    })

    setModal(true)

  }



  const applyColorPreset = (preset) => {

    setForm((f) => ({ ...f, color_name: preset.name, color_hex: preset.hex }))

  }



  const saveMaterial = async (e) => {

    e.preventDefault()

    setSaving(true)

    try {

      const payload = {

        name: form.name.trim(),

        usage_kind: form.usage_kind || 'other',

        color_name: form.color_name.trim(),

        color_hex: form.color_hex,

        sku: form.sku.trim(),

        unit: resolveUnitValue(form.unit_preset, form.unit_custom),

        unit_cost: Number(form.unit_cost) || 0,

        stock: form.stock === '' ? null : Number(form.stock),

        description: form.description.trim(),

        is_active: form.is_active,

      }

      if (editing) {

        await materialsApi.update(editing.id, payload)

      } else {

        await materialsApi.create({
          ...payload,
          auto_approve: isOffice && directApprove,
        })

      }

      setModal(false)

      load()

    } catch (err) {

      setError(err.message)

    } finally {

      setSaving(false)

    }

  }



  const removeMaterial = async (m) => {

    if (!await confirm({

      title: 'حذف متریال',

      message: `متریال «${m.name}» حذف شود؟`,

      confirmText: 'بله، حذف شود',

      variant: 'danger',

    })) return

    try {

      await materialsApi.remove(m.id)

      load()

    } catch (err) {

      setError(err.message)

    }

  }



  const approveMaterial = async (m) => {

    try {

      await materialsApi.approve(m.id)

      load()

    } catch (err) {

      setError(err.message)

    }

  }



  const rejectMaterial = async (m) => {

    const reason = window.prompt('دلیل رد (اختیاری):', '')

    if (reason === null) return

    try {

      await materialsApi.reject(m.id, reason)

      load()

    } catch (err) {

      setError(err.message)

    }

  }



  const showActions = canApprove && isOffice



  return (

    <div className={fromLegacy("page materials-page")}>

      <div className={fromLegacy("products-page-header")}>

        <div>

          <h1 className={fromLegacy("page-title")}>{isOffice ? 'تایید متریال' : 'متریال'}</h1>

        </div>

        {canCreate && !isOffice && (

          <Button type="button" onClick={() => openCreate(false)}>+ متریال</Button>

        )}

        {canApprove && isOffice && (

          <Button type="button" variant="ghost" onClick={() => openCreate(true)}>+ ثبت مستقیم</Button>

        )}

      </div>



      {error && <div className={fromLegacy("alert-error")}>{error}</div>}



      <Card>

        <FilterBar>

          <Field label="جستجو">

            <input

              className={fromLegacy("search-input")}

              value={search}

              onChange={(e) => setSearch(e.target.value)}

              placeholder="نام، رنگ یا کد…"

            />

          </Field>

          {isOffice && (

            <Field label="وضعیت تایید">

              <div className={fromLegacy("workflow-filter-tabs")}>

                {[

                  { value: 'pending', label: 'در انتظار' },

                  { value: 'approved', label: 'تایید شده' },

                  { value: 'rejected', label: 'رد شده' },

                  { value: 'all', label: 'همه' },

                ].map((opt) => (

                  <button

                    key={opt.value}

                    type="button"

                    className={fromLegacy(`workflow-filter-tab ${statusFilter === opt.value ? 'active' : ''}`)}

                    onClick={() => setStatusFilter(opt.value)}

                  >

                    {opt.label}

                  </button>

                ))}

              </div>

            </Field>

          )}

        </FilterBar>



        {loading ? (

          <div className={fromLegacy("loading")}>در حال بارگذاری…</div>

        ) : materials.length === 0 ? (

          <EmptyState text={isOffice && statusFilter === 'pending' ? 'متریالی در انتظار تایید نیست.' : 'متریالی یافت نشد.'} />

        ) : (

          <>
          <div className={fromLegacy("table-wrap materials-table-desktop")}>

            <table className={fromLegacy("table")}>

              <thead>

                <tr>

                  <th>متریال</th>

                  <th>رنگ</th>

                  <th>واحد</th>

                  <th>قیمت واحد</th>

                  <th>موجودی</th>

                  <th>ارزش موجودی</th>

                  <th>وضعیت</th>

                  {showActions && <th />}

                </tr>

              </thead>

              <tbody>

                {materials.map((m) => (

                  <tr key={m.id}>

                    <td>

                      <strong>{m.name}</strong>

                      {m.sku && <div className={fromLegacy("muted small ltr")}>SKU: {m.sku}</div>}

                      {m.submitted_by && <div className={fromLegacy("muted small")}>ثبت: {m.submitted_by}</div>}

                    </td>

                    <td>

                      {m.color_name ? (

                        <span className={fromLegacy("material-color-cell")}>

                          <span

                            className={fromLegacy("color-swatch inline")}

                            style={{

                              background: m.color_hex,

                              borderColor: m.color_hex === '#f8fafc' ? '#cbd5e1' : m.color_hex,

                            }}

                          />

                          {m.color_name}

                        </span>

                      ) : '—'}

                    </td>

                    <td>{m.unit}</td>

                    <td>{formatMoney(m.unit_cost)}</td>

                    <td>{m.stock != null ? m.stock : '—'}</td>

                    <td>{m.inventory_value != null ? formatMoney(m.inventory_value) : '—'}</td>

                    <td>

                      <Badge color={APPROVAL_COLORS[m.approval_status] || '#94a3b8'}>

                        {m.approval_status_display || m.approval_status}

                      </Badge>

                      {m.rejection_reason && (

                        <div className={fromLegacy("muted small")}>{m.rejection_reason}</div>

                      )}

                    </td>

                    {showActions && (

                      <td className={fromLegacy("row-actions")}>

                        {canApprove && m.approval_status === 'pending' && (

                          <>

                            <button type="button" className={fromLegacy("link link-success")} onClick={() => approveMaterial(m)}>تایید</button>

                            <button type="button" className={fromLegacy("link danger")} onClick={() => rejectMaterial(m)}>رد</button>

                          </>

                        )}

                        {canApprove && (

                          <>

                            <button type="button" className={fromLegacy("link")} onClick={() => openEdit(m)}>ویرایش</button>

                            <button type="button" className={fromLegacy("link danger")} onClick={() => removeMaterial(m)}>حذف</button>

                          </>

                        )}

                      </td>

                    )}

                  </tr>

                ))}

              </tbody>

            </table>

          </div>
          <div className={fromLegacy("materials-cards-mobile")}>
            {materials.map((m) => (
              <div key={m.id} className={fromLegacy("m-card")}>
                <div className={fromLegacy("m-card-head")}>
                  <div>
                    <strong>{m.name}</strong>
                    {m.sku && <div className={fromLegacy("muted small ltr")}>SKU: {m.sku}</div>}
                  </div>
                  <Badge color={APPROVAL_COLORS[m.approval_status] || '#94a3b8'}>
                    {m.approval_status_display || m.approval_status}
                  </Badge>
                </div>
                <div className={fromLegacy("m-card-grid")}>
                  <div>
                    <span className={fromLegacy("muted")}>رنگ</span>
                    {m.color_name ? (
                      <span className={fromLegacy("material-color-cell")}>
                        <span className={fromLegacy("color-swatch inline")} style={{ background: m.color_hex, borderColor: m.color_hex === '#f8fafc' ? '#cbd5e1' : m.color_hex }} />
                        {m.color_name}
                      </span>
                    ) : '—'}
                  </div>
                  <div><span className={fromLegacy("muted")}>واحد</span>{m.unit}</div>
                  <div><span className={fromLegacy("muted")}>قیمت واحد</span>{formatMoney(m.unit_cost)}</div>
                  <div><span className={fromLegacy("muted")}>موجودی</span>{m.stock != null ? m.stock : '—'}</div>
                  <div><span className={fromLegacy("muted")}>ارزش موجودی</span>{m.inventory_value != null ? formatMoney(m.inventory_value) : '—'}</div>
                </div>
                {m.rejection_reason && <p className={fromLegacy("muted small")}>{m.rejection_reason}</p>}
                {showActions && (
                  <div className={fromLegacy("m-card-actions")}>
                    {canApprove && m.approval_status === 'pending' && (
                      <>
                        <button type="button" className={fromLegacy("link link-success")} onClick={() => approveMaterial(m)}>تایید</button>
                        <button type="button" className={fromLegacy("link danger")} onClick={() => rejectMaterial(m)}>رد</button>
                      </>
                    )}
                    {canApprove && (
                      <>
                        <button type="button" className={fromLegacy("link")} onClick={() => openEdit(m)}>ویرایش</button>
                        <button type="button" className={fromLegacy("link danger")} onClick={() => removeMaterial(m)}>حذف</button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          <LoadMoreButton
            hasMore={materials.length < total}
            loading={loadingMore}
            onClick={() => load({ append: true, offset: offset + PAGE_SIZE })}
          />
          </>

        )}

      </Card>



      <Modal

        title={editing ? 'ویرایش متریال' : 'متریال جدید'}

        open={modal}

        onClose={() => !saving && setModal(false)}

      >

        <form onSubmit={saveMaterial} className={fromLegacy("form")}>

          <Field label="نام متریال">

            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />

          </Field>

          <Field label="نوع مصرف کارخانه">

            <Select value={form.usage_kind || 'other'} onChange={(v) => setForm({ ...form, usage_kind: v })} options={USAGE_KIND_OPTIONS} />

          </Field>

          <div className={fromLegacy("variant-color-presets")}>

            {COLOR_PRESETS.map((preset) => (

              <button

                key={preset.hex}

                type="button"

                className={fromLegacy("color-preset-btn")}

                title={preset.name}

                style={{ background: preset.hex, borderColor: preset.hex === '#f8fafc' ? '#cbd5e1' : preset.hex }}

                onClick={() => applyColorPreset(preset)}

              />

            ))}

          </div>

          <div className={fromLegacy("form-grid-2")}>

            <Field label="نام رنگ">

              <input value={form.color_name} onChange={(e) => setForm({ ...form, color_name: e.target.value })} placeholder="مثلاً مشکی" />

            </Field>

            <Field label="کد رنگ">

              <input className={fromLegacy("ltr")} type="color" value={form.color_hex} onChange={(e) => setForm({ ...form, color_hex: e.target.value })} />

            </Field>

            <Field label="کد (SKU)">

              <input className={fromLegacy("ltr")} value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />

            </Field>

            <Field label="واحد">

              <UnitSelect

                preset={form.unit_preset}

                customValue={form.unit_custom}

                onPresetChange={(v) => setForm({ ...form, unit_preset: v })}

                onCustomChange={(v) => setForm({ ...form, unit_custom: v })}

              />

            </Field>

            <Field label="قیمت واحد (تمام‌شده)">

              <MoneyInput min="0" value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} required />

            </Field>

            <Field label="موجودی">

              <input className={fromLegacy("ltr")} type="number" min="0" step="0.01" value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} placeholder="—" />

            </Field>

          </div>

          {previewInventoryValue != null && (
            <div className={fromLegacy("material-value-preview")}>
              <span className={fromLegacy("muted")}>ارزش موجودی (موجودی × قیمت واحد):</span>
              <strong>{formatMoney(previewInventoryValue)}</strong>
            </div>
          )}

          <Field label="توضیحات">

            <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

          </Field>

          {isOffice && (

            <label className={fromLegacy("checkbox-row")}>

              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />

              فعال

            </label>

          )}

          <div className={fromLegacy("form-actions")}>

            <Button type="button" variant="ghost" onClick={() => setModal(false)} disabled={saving}>انصراف</Button>

            <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره'}</Button>

          </div>

        </form>

      </Modal>

    </div>

  )

}


