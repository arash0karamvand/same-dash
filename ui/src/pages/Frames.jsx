import { useCallback, useEffect, useMemo, useState } from 'react'
import { framesApi, materialsApi, productsApi } from '../api/client'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { PAGE_SIZE, PICKER_LIMIT } from '../config/pagination'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const DEFAULT_COMPONENTS = [
  { component_type: 'three_seater', default_quantity: 1, material_rules: [] },
  { component_type: 'armchair', default_quantity: 2, material_rules: [] },
  { component_type: 'side_table', default_quantity: 2, material_rules: [] },
  { component_type: 'coffee_table', default_quantity: 1, material_rules: [] },
]

const EMPTY_FRAME = {
  name: '',
  design_style: 'modern',
  wood_type: 'ash_georgian_g1',
  product_id: '',
  is_active: true,
  models: [],
  service_template: {
    name: 'سرویس ۸ نفره',
    default_seat_count: 8,
    components: DEFAULT_COMPONENTS.map((c) => ({ ...c, material_rules: [] })),
  },
}

const EMPTY_WOOD = { label: '', quantity: '1', unit: 'متر', material_id: '' }
const EMPTY_RULE = { rule_key: 'back_fabric', material_id: '', quantity: '1', unit: 'متر', is_default: true }

const TABS = [
  { key: 'basic', label: 'اطلاعات پایه' },
  { key: 'models', label: 'مدل‌ها و چوب' },
  { key: 'service', label: 'سرویس و متریال' },
]

function componentLabel(type, options) {
  return options.component_types?.find((o) => o.value === type)?.label || type
}

export default function Frames() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const canManage = hasPermission(user, 'manage_frames')

  const [frames, setFrames] = useState([])
  const [options, setOptions] = useState({ design_styles: [], wood_types: [], component_types: [], rule_keys: [] })
  const [materials, setMaterials] = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_FRAME)
  const [tab, setTab] = useState('basic')
  const [saving, setSaving] = useState(false)

  const materialOptions = useMemo(
    () => materials.map((m) => ({ value: String(m.id), label: `${m.name}${m.color_name ? ` (${m.color_name})` : ''}` })),
    [materials],
  )
  const productOptions = useMemo(
    () => [{ value: '', label: 'بدون اتصال' }, ...products.map((p) => ({ value: String(p.id), label: p.name }))],
    [products],
  )

  const loadFrames = useCallback(async (reset = false) => {
    setLoading(true)
    setError('')
    try {
      const nextOffset = reset ? 0 : offset
      const data = await framesApi.list({ search: search.trim(), offset: nextOffset, limit: PAGE_SIZE })
      const results = data.results || []
      setFrames((prev) => (reset ? results : [...prev, ...results]))
      setHasMore(Boolean(data.has_more))
      if (reset) setOffset(results.length)
      else setOffset(nextOffset + results.length)
    } catch (err) {
      setError(err.message || 'خطا در بارگذاری کلاف‌ها')
    } finally {
      setLoading(false)
    }
  }, [offset, search])

  useEffect(() => {
    loadFrames(true)
  }, [search])

  useEffect(() => {
    Promise.all([
      framesApi.options().catch(() => ({})),
      materialsApi.list({ limit: PICKER_LIMIT, approved_only: true }).catch(() => ({ results: [] })),
      productsApi.list({ limit: PICKER_LIMIT }).catch(() => ({ results: [] })),
    ]).then(([opts, mats, prods]) => {
      setOptions(opts || {})
      setMaterials(mats.results || [])
      setProducts(prods.results || [])
    })
  }, [])

  const openCreate = () => {
    setEditing(null)
    setForm({
      ...EMPTY_FRAME,
      service_template: {
        ...EMPTY_FRAME.service_template,
        components: DEFAULT_COMPONENTS.map((c) => ({ ...c, material_rules: [] })),
      },
    })
    setTab('basic')
    setModalOpen(true)
  }

  const openEdit = async (frame) => {
    try {
      const full = await framesApi.get(frame.id)
      setEditing(full)
      setForm({
        name: full.name || '',
        design_style: full.design_style || 'modern',
        wood_type: full.wood_type || 'ash_georgian_g1',
        product_id: full.product_id ? String(full.product_id) : '',
        is_active: full.is_active !== false,
        models: (full.models || []).map((m) => ({
          id: m.id,
          name: m.name,
          sort_order: m.sort_order,
          is_active: m.is_active !== false,
          wood_requirements: (m.wood_requirements || []).map((w) => ({
            id: w.id,
            label: w.label || '',
            quantity: String(w.quantity ?? 1),
            unit: w.unit || 'متر',
            material_id: w.material_id ? String(w.material_id) : '',
          })),
        })),
        service_template: {
          name: full.service_template?.name || 'سرویس ۸ نفره',
          default_seat_count: full.service_template?.default_seat_count || 8,
          components: (full.service_template?.components?.length
            ? full.service_template.components
            : DEFAULT_COMPONENTS
          ).map((c) => ({
            id: c.id,
            component_type: c.component_type,
            default_quantity: c.default_quantity ?? 1,
            material_rules: (c.material_rules || []).map((r) => ({
              id: r.id,
              rule_key: r.rule_key,
              material_id: r.material_id ? String(r.material_id) : '',
              quantity: String(r.quantity ?? 1),
              unit: r.unit || 'متر',
              is_default: r.is_default !== false,
            })),
          })),
        },
      })
      setTab('basic')
      setModalOpen(true)
    } catch (err) {
      setError(err.message || 'خطا در بارگذاری کلاف')
    }
  }

  const saveFrame = async (e) => {
    e.preventDefault()
    if (!canManage) return
    setSaving(true)
    setError('')
    try {
      const payload = {
        name: form.name.trim(),
        design_style: form.design_style,
        wood_type: form.wood_type,
        product_id: form.product_id ? Number(form.product_id) : null,
        is_active: form.is_active,
        models: form.models.map((m) => ({
          id: m.id,
          name: m.name.trim(),
          is_active: m.is_active !== false,
          wood_requirements: (m.wood_requirements || [])
            .filter((w) => w.label?.trim() || w.material_id)
            .map((w) => ({
              id: w.id,
              label: w.label?.trim() || '',
              quantity: Number(w.quantity) || 1,
              unit: w.unit || 'متر',
              material_id: w.material_id ? Number(w.material_id) : null,
            })),
        })),
        service_template: {
          name: form.service_template.name,
          default_seat_count: Number(form.service_template.default_seat_count) || 8,
          components: form.service_template.components.map((c) => ({
            id: c.id,
            component_type: c.component_type,
            default_quantity: Number(c.default_quantity) || 1,
            material_rules: (c.material_rules || [])
              .filter((r) => r.material_id)
              .map((r) => ({
                id: r.id,
                rule_key: r.rule_key,
                material_id: Number(r.material_id),
                quantity: Number(r.quantity) || 1,
                unit: r.unit || 'متر',
                is_default: r.is_default !== false,
              })),
          })),
        },
      }
      if (editing?.id) await framesApi.update(editing.id, payload)
      else await framesApi.create(payload)
      setModalOpen(false)
      loadFrames(true)
    } catch (err) {
      setError(err.message || 'خطا در ذخیره کلاف')
    } finally {
      setSaving(false)
    }
  }

  const removeFrame = async (frame) => {
    if (!canManage) return
    const ok = await confirm(`کلاف «${frame.name}» حذف شود؟`)
    if (!ok) return
    try {
      await framesApi.remove(frame.id)
      loadFrames(true)
    } catch (err) {
      setError(err.message || 'خطا در حذف')
    }
  }

  const addModel = () => {
    setForm((f) => ({
      ...f,
      models: [...f.models, { name: '', is_active: true, wood_requirements: [{ ...EMPTY_WOOD }] }],
    }))
  }

  const updateModel = (idx, key, val) => {
    setForm((f) => ({
      ...f,
      models: f.models.map((m, i) => (i === idx ? { ...m, [key]: val } : m)),
    }))
  }

  const removeModel = (idx) => {
    setForm((f) => ({ ...f, models: f.models.filter((_, i) => i !== idx) }))
  }

  const addWoodRow = (modelIdx) => {
    setForm((f) => ({
      ...f,
      models: f.models.map((m, i) =>
        i === modelIdx ? { ...m, wood_requirements: [...(m.wood_requirements || []), { ...EMPTY_WOOD }] } : m,
      ),
    }))
  }

  const updateWoodRow = (modelIdx, rowIdx, key, val) => {
    setForm((f) => ({
      ...f,
      models: f.models.map((m, i) =>
        i === modelIdx
          ? {
              ...m,
              wood_requirements: m.wood_requirements.map((w, j) => (j === rowIdx ? { ...w, [key]: val } : w)),
            }
          : m,
      ),
    }))
  }

  const removeWoodRow = (modelIdx, rowIdx) => {
    setForm((f) => ({
      ...f,
      models: f.models.map((m, i) =>
        i === modelIdx
          ? { ...m, wood_requirements: m.wood_requirements.filter((_, j) => j !== rowIdx) }
          : m,
      ),
    }))
  }

  const updateComponent = (idx, key, val) => {
    setForm((f) => ({
      ...f,
      service_template: {
        ...f.service_template,
        components: f.service_template.components.map((c, i) => (i === idx ? { ...c, [key]: val } : c)),
      },
    }))
  }

  const addRule = (compIdx) => {
    const comp = form.service_template.components[compIdx]
    const rule = hasBackOption(comp.component_type)
      ? { ...EMPTY_RULE }
      : { ...EMPTY_RULE, rule_key: 'extra' }
    setForm((f) => ({
      ...f,
      service_template: {
        ...f.service_template,
        components: f.service_template.components.map((c, i) =>
          i === compIdx ? { ...c, material_rules: [...(c.material_rules || []), rule] } : c,
        ),
      },
    }))
  }

  const updateRule = (compIdx, ruleIdx, key, val) => {
    setForm((f) => ({
      ...f,
      service_template: {
        ...f.service_template,
        components: f.service_template.components.map((c, i) =>
          i === compIdx
            ? {
                ...c,
                material_rules: c.material_rules.map((r, j) => (j === ruleIdx ? { ...r, [key]: val } : r)),
              }
            : c,
        ),
      },
    }))
  }

  const removeRule = (compIdx, ruleIdx) => {
    setForm((f) => ({
      ...f,
      service_template: {
        ...f.service_template,
        components: f.service_template.components.map((c, i) =>
          i === compIdx
            ? { ...c, material_rules: c.material_rules.filter((_, j) => j !== ruleIdx) }
            : c,
        ),
      },
    }))
  }

  const hasBackOption = (type) => type === 'three_seater' || type === 'armchair'

  return (
    <div className={fromLegacy('page frames-page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>کلاف‌ها</h1>
          <p className={fromLegacy('muted')}>تعریف کلاف، مدل، میزان چوب و سرویس مبلمان</p>
        </div>
        {canManage && <Button onClick={openCreate}>+ کلاف جدید</Button>}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <FilterBar search={search} onSearchChange={setSearch} searchPlaceholder="جستجوی نام کلاف یا مدل…" />

      <Card>
        {loading && frames.length === 0 ? (
          <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
        ) : frames.length === 0 ? (
          <EmptyState title="کلافی ثبت نشده" description="اولین کلاف را اضافه کنید." />
        ) : (
          <div className={fromLegacy('frame-list')}>
            {frames.map((frame) => (
              <div key={frame.id} className={fromLegacy('frame-row')}>
                <div className={fromLegacy('frame-row-main')}>
                  <strong>{frame.name}</strong>
                  <div className={fromLegacy('frame-row-meta muted small')}>
                    <span>{frame.design_style_display}</span>
                    <span>•</span>
                    <span>{frame.wood_type_display}</span>
                    <span>•</span>
                    <span>{(frame.models || []).length} مدل</span>
                  </div>
                </div>
                <div className={fromLegacy('row-actions')}>
                  {!frame.is_active && <Badge color="var(--muted)">غیرفعال</Badge>}
                  <button type="button" className={fromLegacy('link')} onClick={() => openEdit(frame)}>ویرایش</button>
                  {canManage && (
                    <button type="button" className={fromLegacy('link danger')} onClick={() => removeFrame(frame)}>حذف</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        <LoadMoreButton visible={hasMore} loading={loading} onClick={() => loadFrames(false)} />
      </Card>

      <Modal
        title={editing ? 'ویرایش کلاف' : 'کلاف جدید'}
        open={modalOpen}
        onClose={() => !saving && setModalOpen(false)}
        wide
      >
        <div className={fromLegacy('frame-tabs')}>
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={fromLegacy(`frame-tab${tab === t.key ? ' active' : ''}`)}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <form onSubmit={saveFrame} className={fromLegacy('form frame-form')}>
          {tab === 'basic' && (
            <div className={fromLegacy('form-grid-2')}>
              <Field label="نام کلاف (برای چه مدلی)">
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </Field>
              <Field label="سبک طراحی">
                <Select
                  value={form.design_style}
                  onChange={(v) => setForm({ ...form, design_style: v })}
                  options={(options.design_styles || []).map((o) => ({ value: o.value, label: o.label }))}
                />
              </Field>
              <Field label="جنس چوب اصلی">
                <Select
                  value={form.wood_type}
                  onChange={(v) => setForm({ ...form, wood_type: v })}
                  options={(options.wood_types || []).map((o) => ({ value: o.value, label: o.label }))}
                />
              </Field>
              <Field label="اتصال به محصول (اختیاری)">
                <Select
                  value={form.product_id}
                  onChange={(v) => setForm({ ...form, product_id: v })}
                  options={productOptions}
                  placeholder="انتخاب محصول"
                />
              </Field>
              <label className={fromLegacy('checkbox-row')}>
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                فعال
              </label>
            </div>
          )}

          {tab === 'models' && (
            <div className={fromLegacy('frame-models-section')}>
              <div className={fromLegacy('section-head')}>
                <h4>مدل‌های کلاف</h4>
                {canManage && <Button type="button" variant="ghost" onClick={addModel}>+ مدل</Button>}
              </div>
              {form.models.length === 0 && <p className={fromLegacy('muted small')}>مدلی تعریف نشده.</p>}
              {form.models.map((model, modelIdx) => (
                <div key={modelIdx} className={fromLegacy('frame-model-block')}>
                  <div className={fromLegacy('form-grid-2')}>
                    <Field label="نام مدل">
                      <input value={model.name} onChange={(e) => updateModel(modelIdx, 'name', e.target.value)} required />
                    </Field>
                    <div className={fromLegacy('row-actions')}>
                      <Button type="button" variant="ghost" onClick={() => addWoodRow(modelIdx)}>+ ردیف چوب</Button>
                      <button type="button" className={fromLegacy('link danger')} onClick={() => removeModel(modelIdx)}>حذف مدل</button>
                    </div>
                  </div>
                  {(model.wood_requirements || []).map((wood, rowIdx) => (
                    <div key={rowIdx} className={fromLegacy('variant-row product-material-row')}>
                      <div className={fromLegacy('form-grid-2 variant-fields')}>
                        <Field label="برچسب">
                          <input value={wood.label} onChange={(e) => updateWoodRow(modelIdx, rowIdx, 'label', e.target.value)} placeholder="مثلاً قاب اصلی" />
                        </Field>
                        <Field label="مقدار">
                          <input className={fromLegacy('ltr')} type="number" min="0.001" step="0.001" value={wood.quantity} onChange={(e) => updateWoodRow(modelIdx, rowIdx, 'quantity', e.target.value)} />
                        </Field>
                        <Field label="واحد">
                          <Select
                            value={wood.unit}
                            onChange={(v) => updateWoodRow(modelIdx, rowIdx, 'unit', v)}
                            options={[{ value: 'متر', label: 'متر' }, { value: 'عدد', label: 'عدد' }]}
                          />
                        </Field>
                        <Field label="متریال (اختیاری)">
                          <Select
                            value={wood.material_id}
                            onChange={(v) => updateWoodRow(modelIdx, rowIdx, 'material_id', v)}
                            options={[{ value: '', label: '—' }, ...materialOptions]}
                            placeholder="انتخاب متریال"
                          />
                        </Field>
                      </div>
                      <button type="button" className={fromLegacy('link danger variant-remove')} onClick={() => removeWoodRow(modelIdx, rowIdx)}>حذف</button>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {tab === 'service' && (
            <div className={fromLegacy('frame-service-section')}>
              <div className={fromLegacy('form-grid-2')}>
                <Field label="نام سرویس">
                  <input
                    value={form.service_template.name}
                    onChange={(e) => setForm({ ...form, service_template: { ...form.service_template, name: e.target.value } })}
                  />
                </Field>
                <Field label="تعداد نفر پیش‌فرض">
                  <input
                    className={fromLegacy('ltr')}
                    type="number"
                    min="1"
                    value={form.service_template.default_seat_count}
                    onChange={(e) => setForm({ ...form, service_template: { ...form.service_template, default_seat_count: e.target.value } })}
                  />
                </Field>
              </div>
              {form.service_template.components.map((comp, compIdx) => (
                <div key={comp.component_type || compIdx} className={fromLegacy('frame-component-block')}>
                  <div className={fromLegacy('section-head')}>
                    <h4>{componentLabel(comp.component_type, options)}</h4>
                    <Button type="button" variant="ghost" onClick={() => addRule(compIdx)}>
                      + {hasBackOption(comp.component_type) ? 'قانون متریال' : 'متریال اضافه'}
                    </Button>
                  </div>
                  <Field label="تعداد پیش‌فرض">
                    <input
                      className={fromLegacy('ltr')}
                      type="number"
                      min="0"
                      value={comp.default_quantity}
                      onChange={(e) => updateComponent(compIdx, 'default_quantity', e.target.value)}
                    />
                  </Field>
                  {(comp.material_rules || []).map((rule, ruleIdx) => (
                    <div key={ruleIdx} className={fromLegacy('variant-row product-material-row')}>
                      <div className={fromLegacy('form-grid-2 variant-fields')}>
                        {hasBackOption(comp.component_type) && (
                          <Field label="نوع">
                            <Select
                              value={rule.rule_key}
                              onChange={(v) => updateRule(compIdx, ruleIdx, 'rule_key', v)}
                              options={(options.rule_keys || [])
                                .filter((o) => o.value === 'back_fabric' || o.value === 'back_wood')
                                .map((o) => ({ value: o.value, label: o.label }))}
                            />
                          </Field>
                        )}
                        {!hasBackOption(comp.component_type) && (
                          <Field label="نوع">
                            <input disabled value="متریال اضافه" />
                          </Field>
                        )}
                        <Field label="متریال">
                          <Select
                            value={rule.material_id}
                            onChange={(v) => updateRule(compIdx, ruleIdx, 'material_id', v)}
                            options={[{ value: '', label: 'انتخاب…' }, ...materialOptions]}
                          />
                        </Field>
                        <Field label="مقدار">
                          <input className={fromLegacy('ltr')} type="number" min="0.001" step="0.001" value={rule.quantity} onChange={(e) => updateRule(compIdx, ruleIdx, 'quantity', e.target.value)} />
                        </Field>
                        <Field label="واحد">
                          <Select
                            value={rule.unit}
                            onChange={(v) => updateRule(compIdx, ruleIdx, 'unit', v)}
                            options={[{ value: 'متر', label: 'متر' }, { value: 'عدد', label: 'عدد' }]}
                          />
                        </Field>
                      </div>
                      <button type="button" className={fromLegacy('link danger variant-remove')} onClick={() => removeRule(compIdx, ruleIdx)}>حذف</button>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          <div className={fromLegacy('form-actions')}>
            <Button type="button" variant="ghost" onClick={() => setModalOpen(false)} disabled={saving}>انصراف</Button>
            {canManage && <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره کلاف'}</Button>}
          </div>
        </form>
      </Modal>
    </div>
  )
}
