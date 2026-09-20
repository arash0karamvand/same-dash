import { useCallback, useEffect, useMemo, useState } from 'react'
import { materialsApi, workshopRecipesApi } from '../api/client'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { parseRoute } from '../utils/routing'
import { hasAnyPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const KIND_PAGES = {
  'factory-paint-recipes': { kind: 'paint', title: 'رنگ‌ها', usageKind: 'paint', nameLabel: 'نام رنگ' },
  'factory-fabric-recipes': { kind: 'fabric', title: 'پارچه‌ها', usageKind: 'fabric', nameLabel: 'نام پارچه' },
  'factory-foam-recipes': { kind: 'foam', title: 'اسفنج‌ها', usageKind: 'foam', nameLabel: 'نام اسفنج' },
  'factory-webbing-recipes': { kind: 'webbing', title: 'تسمه‌ها', usageKind: 'webbing', nameLabel: 'نام تسمه' },
  'factory-cushion-recipes': { kind: 'cushion', title: 'کوسن‌ها', usageKind: 'cushion', nameLabel: 'نام کوسن' },
}

const EMPTY = { name: '', color_name: '', note: '', is_active: true, materials: [] }

export default function WorkshopRecipes() {
  const { page } = parseRoute()
  const meta = KIND_PAGES[page] || KIND_PAGES['factory-paint-recipes']
  const { user } = useAuth()
  const confirm = useConfirm()
  const canManage = hasAnyPermission(user, ['manage_factory_products', 'manage_materials'])
  useRegisterPageGuide(page, PAGE_GUIDE_DEFAULTS[page])

  const [recipes, setRecipes] = useState([])
  const [materials, setMaterials] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)

  const materialOptions = useMemo(
    () => materials.map((m) => ({
      value: String(m.id),
      label: m.color_name ? `${m.name} (${m.color_name})` : m.name,
    })),
    [materials],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [list, mats] = await Promise.all([
        workshopRecipesApi.list({ kind: meta.kind, search: search.trim(), include_inactive: canManage ? '1' : undefined, limit: 200 }),
        materialsApi.list({ limit: 300, approved_only: true, usage_kind: meta.usageKind }).catch(() => ({ results: [] })),
      ])
      setRecipes(list.results || [])
      setMaterials(mats.results || [])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [meta.kind, meta.usageKind, search, canManage])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY, materials: [] })
    setModalOpen(true)
  }

  const openEdit = (recipe) => {
    setEditing(recipe)
    setForm({
      name: recipe.name || '',
      color_name: recipe.color_name || '',
      note: recipe.note || '',
      is_active: recipe.is_active !== false,
      materials: (recipe.materials || []).map((row) => ({
        material_id: String(row.material_id),
        quantity: String(row.quantity ?? 1),
        unit: row.unit || '',
      })),
    })
    setModalOpen(true)
  }

  const updateRow = (idx, key, val) => {
    setForm((f) => ({
      ...f,
      materials: f.materials.map((row, i) => (i === idx ? { ...row, [key]: val } : row)),
    }))
  }

  const save = async () => {
    setSaving(true)
    try {
      const payload = {
        kind: meta.kind,
        name: form.name.trim(),
        color_name: form.color_name.trim(),
        note: form.note.trim(),
        is_active: form.is_active,
        materials: form.materials
          .filter((row) => row.material_id)
          .map((row) => ({
            material_id: Number(row.material_id),
            quantity: Number(row.quantity) || 1,
            unit: row.unit || '',
          })),
      }
      if (editing) await workshopRecipesApi.update(editing.id, payload)
      else await workshopRecipesApi.create(payload)
      setModalOpen(false)
      setEditing(null)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeRecipe = async (recipe) => {
    if (!(await confirm({ title: 'حذف دستور', message: `${recipe.name} حذف شود؟` }))) return
    try {
      await workshopRecipesApi.remove(recipe.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className={fromLegacy('page')}>
      <div className={fromLegacy('page-head')}>
        <div>
          <h1>کاتالوگ {meta.title}</h1>
          <p className={fromLegacy('muted')}>دستور دست‌کار برای محصول — بدون رکورد نمونه؛ فقط تعریف قابلیت</p>
        </div>
        {canManage && <Button onClick={openCreate}>+ دستور جدید</Button>}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      <FilterBar>
        <Field label="جستجو">
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="نام یا فام…" />
        </Field>
      </FilterBar>

      {loading ? (
        <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
      ) : recipes.length === 0 ? (
        <EmptyState text="دستوری تعریف نشده." />
      ) : (
        <Card>
          {recipes.map((recipe) => (
            <div key={recipe.id} className={fromLegacy('frame-row')}>
              <div>
                <strong>{recipe.name}</strong>
                {!recipe.is_active && <Badge>غیرفعال</Badge>}
                <div className={fromLegacy('muted small')}>
                  {recipe.color_name || 'بدون فام'}
                  {(recipe.materials || []).length > 0 && ` • ${(recipe.materials || []).length} متریال`}
                </div>
                {(recipe.materials || []).length > 0 && (
                  <ul className={fromLegacy('muted small')}>
                    {recipe.materials.map((row) => (
                      <li key={row.id || row.material_id}>
                        {row.material_name}
                        {row.material_color ? ` (${row.material_color})` : ''}
                        {' × '}{row.quantity} {row.unit}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {canManage && (
                <div className={fromLegacy('row')}>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(recipe)}>ویرایش</Button>
                  <Button variant="ghost" size="sm" onClick={() => removeRecipe(recipe)}>حذف</Button>
                </div>
              )}
            </div>
          ))}
        </Card>
      )}

      <Modal title={editing ? `ویرایش ${editing.name}` : `دستور ${meta.title}`} open={modalOpen} onClose={() => setModalOpen(false)}>
        <Field label={meta.nameLabel}>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="رنگ / فام / کد">
          <input value={form.color_name} onChange={(e) => setForm({ ...form, color_name: e.target.value })} />
        </Field>
        <Field label="توضیحات">
          <textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
        </Field>
        <div className={fromLegacy('section-head')}>
          <h4>متریال مصرفی</h4>
          {canManage && (
            <Button type="button" variant="ghost" onClick={() => setForm({ ...form, materials: [...form.materials, { material_id: '', quantity: '1', unit: '' }] })}>+ متریال</Button>
          )}
        </div>
        {form.materials.map((row, idx) => (
          <div key={idx} className={fromLegacy('form-grid-2')}>
            <Field label="متریال">
              <Select
                value={row.material_id}
                onChange={(v) => updateRow(idx, 'material_id', v)}
                options={[{ value: '', label: 'انتخاب…' }, ...materialOptions]}
              />
            </Field>
            <Field label="مقدار">
              <input className={fromLegacy('ltr')} type="number" min="0.001" step="0.001" value={row.quantity} onChange={(e) => updateRow(idx, 'quantity', e.target.value)} />
            </Field>
            <button type="button" className={fromLegacy('link danger')} onClick={() => setForm({ ...form, materials: form.materials.filter((_, i) => i !== idx) })}>حذف</button>
          </div>
        ))}
        <label className={fromLegacy('checkbox-row')}>
          <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
          فعال
        </label>
        <Button disabled={saving} onClick={save}>{saving ? 'در حال ذخیره…' : 'ذخیره'}</Button>
      </Modal>
    </div>
  )
}
