import { useCallback, useEffect, useMemo, useState } from 'react'

import { materialsApi } from '../api/client'

import MoneyInput from '../components/MoneyInput'

import UnitSelect, { resolveUnitValue, splitUnitValue } from '../components/UnitSelect'

import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'

import { useAuth } from '../context/AuthContext'

import { useConfirm } from '../context/ConfirmContext'

import { formatMoney } from '../utils/format'

import { parseRoute } from '../utils/routing'

import { hasPermission } from '../utils/permissions'



const COLOR_PRESETS = [

  { name: 'قرمز', hex: '#ef4444' },

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

  pending: '#f59e0b',

  approved: '#10b981',

  rejected: '#ef4444',

}



const EMPTY_MATERIAL = {

  name: '',

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



  const [materials, setMaterials] = useState([])

  const [loading, setLoading] = useState(true)

  const [error, setError] = useState('')

  const [search, setSearch] = useState('')

  const [statusFilter, setStatusFilter] = useState(isOffice ? 'pending' : 'all')

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

  const load = useCallback(async () => {

    setLoading(true)

    try {

      const data = await materialsApi.list({

        search: search.trim(),

        limit: 200,

        include_pending: !isOffice || statusFilter !== 'approved',

        approval_status: isOffice && statusFilter !== 'all' ? statusFilter : undefined,

        include_inactive: canApprove,

      })

      setMaterials(data.results || [])

      setError('')

    } catch (e) {

      setError(e.message)

    } finally {

      setLoading(false)

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

    <div className="page materials-page">

      <div className="products-page-header">

        <div>

          <h1 className="page-title">{isOffice ? 'تایید متریال' : 'متریال'}</h1>

          <p className="muted">

            {isOffice && 'بررسی، تایید، ویرایش و حذف متریال‌های ثبت‌شده توسط کارخانه'}

            {!isOffice && 'ثبت متریال جدید — پس از ثبت «در انتظار تایید» می‌ماند و از بخش اداری تایید می‌شود؛ موجودی فقط با پایان ساخت کم می‌شود'}

          </p>

        </div>

        {canCreate && !isOffice && (

          <Button type="button" onClick={() => openCreate(false)}>+ متریال</Button>

        )}

        {canApprove && isOffice && (

          <Button type="button" variant="ghost" onClick={() => openCreate(true)}>+ ثبت مستقیم</Button>

        )}

      </div>



      {error && <div className="alert-error">{error}</div>}



      <Card>

        <FilterBar>

          <Field label="جستجو">

            <input

              className="search-input"

              value={search}

              onChange={(e) => setSearch(e.target.value)}

              placeholder="نام، رنگ یا کد…"

            />

          </Field>

          {isOffice && (

            <Field label="وضعیت تایید">

              <div className="workflow-filter-tabs">

                {[

                  { value: 'pending', label: 'در انتظار' },

                  { value: 'approved', label: 'تایید شده' },

                  { value: 'rejected', label: 'رد شده' },

                  { value: 'all', label: 'همه' },

                ].map((opt) => (

                  <button

                    key={opt.value}

                    type="button"

                    className={`workflow-filter-tab ${statusFilter === opt.value ? 'active' : ''}`}

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

          <div className="loading">در حال بارگذاری…</div>

        ) : materials.length === 0 ? (

          <EmptyState text={isOffice && statusFilter === 'pending' ? 'متریالی در انتظار تایید نیست.' : 'متریالی یافت نشد.'} />

        ) : (

          <div className="table-wrap">

            <table className="table">

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

                      {m.sku && <div className="muted small ltr">SKU: {m.sku}</div>}

                      {m.submitted_by && <div className="muted small">ثبت: {m.submitted_by}</div>}

                    </td>

                    <td>

                      {m.color_name ? (

                        <span className="material-color-cell">

                          <span

                            className="color-swatch inline"

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

                        <div className="muted small">{m.rejection_reason}</div>

                      )}

                    </td>

                    {showActions && (

                      <td className="row-actions">

                        {canApprove && m.approval_status === 'pending' && (

                          <>

                            <button type="button" className="link" onClick={() => approveMaterial(m)}>تایید</button>

                            <button type="button" className="link danger" onClick={() => rejectMaterial(m)}>رد</button>

                          </>

                        )}

                        {canApprove && (

                          <>

                            <button type="button" className="link" onClick={() => openEdit(m)}>ویرایش</button>

                            <button type="button" className="link danger" onClick={() => removeMaterial(m)}>حذف</button>

                          </>

                        )}

                      </td>

                    )}

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        )}

      </Card>



      <Modal

        title={editing ? 'ویرایش متریال' : 'متریال جدید'}

        open={modal}

        onClose={() => !saving && setModal(false)}

      >

        <form onSubmit={saveMaterial} className="form">

          {!isOffice && !editing && (

            <p className="muted small" style={{ marginBottom: 12 }}>

              پس از ثبت، متریال قابل ویرایش نیست و تا تایید اداری «در انتظار تایید» می‌ماند.
              موجودی فقط هنگام «پایان ساخت» سفارش در کارخانه کسر می‌شود.

            </p>

          )}

          <Field label="نام متریال">

            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />

          </Field>

          <div className="variant-color-presets">

            {COLOR_PRESETS.map((preset) => (

              <button

                key={preset.hex}

                type="button"

                className="color-preset-btn"

                title={preset.name}

                style={{ background: preset.hex, borderColor: preset.hex === '#f8fafc' ? '#cbd5e1' : preset.hex }}

                onClick={() => applyColorPreset(preset)}

              />

            ))}

          </div>

          <div className="form-grid-2">

            <Field label="نام رنگ">

              <input value={form.color_name} onChange={(e) => setForm({ ...form, color_name: e.target.value })} placeholder="مثلاً مشکی" />

            </Field>

            <Field label="کد رنگ">

              <input className="ltr" type="color" value={form.color_hex} onChange={(e) => setForm({ ...form, color_hex: e.target.value })} />

            </Field>

            <Field label="کد (SKU)">

              <input className="ltr" value={form.sku} onChange={(e) => setForm({ ...form, sku: e.target.value })} />

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

              <input className="ltr" type="number" min="0" step="0.01" value={form.stock} onChange={(e) => setForm({ ...form, stock: e.target.value })} placeholder="—" />

            </Field>

          </div>

          {previewInventoryValue != null && (
            <div className="material-value-preview">
              <span className="muted">ارزش موجودی (موجودی × قیمت واحد):</span>
              <strong>{formatMoney(previewInventoryValue)}</strong>
              {isOffice && (
                <span className="muted small"> — پس از تایید، سند حسابداری ثبت می‌شود</span>
              )}
            </div>
          )}

          <Field label="توضیحات">

            <textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />

          </Field>

          {isOffice && (

            <label className="checkbox-row">

              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />

              فعال

            </label>

          )}

          <div className="form-actions">

            <Button type="button" variant="ghost" onClick={() => setModal(false)} disabled={saving}>انصراف</Button>

            <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره'}</Button>

          </div>

        </form>

      </Modal>

    </div>

  )

}


