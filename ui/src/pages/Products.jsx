import { useCallback, useEffect, useMemo, useState } from 'react'
import { productsApi } from '../api/client'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatMoney } from '../utils/format'

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

const EMPTY_CATEGORY = { name: '', description: '', color: '#6366f1', icon: '📦', sort_order: 0, is_active: true }
const EMPTY_VARIANT = { color_name: '', color_hex: '#cccccc', sku: '', stock: '', is_active: true }
const EMPTY_PRODUCT = {
  name: '',
  sku: '',
  brand: '',
  product_model: '',
  fabric: '',
  description: '',
  unit: 'عدد',
  category_id: '',
  default_price: '',
  is_active: true,
  attributes: {},
  variants: [{ ...EMPTY_VARIANT }],
}

export default function Products() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const canManage = hasPermission(user, 'manage_products')

  const [categories, setCategories] = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')

  const [productModal, setProductModal] = useState(false)
  const [categoryModal, setCategoryModal] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [editingCategory, setEditingCategory] = useState(null)
  const [productForm, setProductForm] = useState(EMPTY_PRODUCT)
  const [categoryForm, setCategoryForm] = useState(EMPTY_CATEGORY)
  const [saving, setSaving] = useState(false)
  const [topSelling, setTopSelling] = useState([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [cats, prods, topData] = await Promise.all([
        productsApi.categories({ active: canManage ? undefined : true }),
        productsApi.list({
          search: search.trim(),
          category_id: categoryFilter || undefined,
          limit: 100,
          include_inactive: canManage,
        }),
        productsApi.topSelling(20).catch(() => ({ results: [] })),
      ])
      setCategories(cats.results || [])
      setProducts(prods.results || [])
      setTopSelling(topData.results || [])
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [search, categoryFilter, canManage])

  useEffect(() => { load() }, [load])

  const categoryOptions = useMemo(
    () => [{ value: '', label: 'همه دسته‌ها' }, ...categories.map((c) => ({ value: String(c.id), label: c.name }))],
    [categories],
  )

  const openCreateProduct = () => {
    setEditingProduct(null)
    setProductForm({ ...EMPTY_PRODUCT, variants: [{ ...EMPTY_VARIANT }] })
    setProductModal(true)
  }

  const openEditProduct = (p) => {
    setEditingProduct(p)
    setProductForm({
      name: p.name,
      sku: p.sku || '',
      brand: p.brand || '',
      product_model: p.product_model || '',
      fabric: p.fabric || '',
      description: p.description || '',
      unit: p.unit || 'عدد',
      category_id: p.category_id ? String(p.category_id) : '',
      default_price: String(p.default_price ?? p.display_price ?? ''),
      is_active: p.is_active,
      attributes: { ...(p.attributes || {}) },
      variants: (p.variants?.length ? p.variants : [{ ...EMPTY_VARIANT }]).map((v) => ({
        id: v.id,
        color_name: v.color_name,
        color_hex: v.color_hex,
        sku: v.sku || '',
        stock: v.stock != null ? String(v.stock) : '',
        is_active: v.is_active !== false,
      })),
    })
    setProductModal(true)
  }

  const openCreateCategory = () => {
    setEditingCategory(null)
    setCategoryForm(EMPTY_CATEGORY)
    setCategoryModal(true)
  }

  const openEditCategory = (c) => {
    setEditingCategory(c)
    setCategoryForm({
      name: c.name,
      description: c.description || '',
      color: c.color || '#6366f1',
      icon: c.icon || '📦',
      sort_order: c.sort_order || 0,
      is_active: c.is_active !== false,
    })
    setCategoryModal(true)
  }

  const updateVariant = (idx, key, val) => {
    setProductForm((f) => ({
      ...f,
      variants: f.variants.map((v, i) => (i === idx ? { ...v, [key]: val } : v)),
    }))
  }

  const addVariant = () => {
    setProductForm((f) => ({ ...f, variants: [...f.variants, { ...EMPTY_VARIANT }] }))
  }

  const removeVariant = (idx) => {
    setProductForm((f) => ({
      ...f,
      variants: f.variants.length > 1 ? f.variants.filter((_, i) => i !== idx) : f.variants,
    }))
  }

  const applyColorPreset = (idx, preset) => {
    updateVariant(idx, 'color_name', preset.name)
    updateVariant(idx, 'color_hex', preset.hex)
  }

  const saveProduct = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        name: productForm.name.trim(),
        sku: productForm.sku.trim(),
        brand: productForm.brand.trim(),
        product_model: productForm.product_model.trim(),
        fabric: productForm.fabric.trim(),
        description: productForm.description.trim(),
        unit: productForm.unit.trim() || 'عدد',
        category_id: productForm.category_id ? Number(productForm.category_id) : null,
        default_price: Number(productForm.default_price) || 0,
        is_active: productForm.is_active,
        attributes: productForm.attributes,
        variants: productForm.variants
          .filter((v) => v.color_name.trim())
          .map((v) => ({
            id: v.id,
            color_name: v.color_name.trim(),
            color_hex: v.color_hex,
            sku: v.sku.trim(),
            stock: v.stock === '' ? null : Number(v.stock),
            is_active: v.is_active !== false,
          })),
      }
      if (editingProduct) {
        await productsApi.update(editingProduct.id, payload)
      } else {
        await productsApi.create(payload)
      }
      setProductModal(false)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const saveCategory = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        ...categoryForm,
        sort_order: Number(categoryForm.sort_order) || 0,
      }
      if (editingCategory) {
        await productsApi.updateCategory(editingCategory.id, payload)
      } else {
        await productsApi.createCategory(payload)
      }
      setCategoryModal(false)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeProduct = async (p) => {
    if (!await confirm({
      title: 'حذف محصول',
      message: `محصول «${p.name}» حذف شود؟`,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    try {
      await productsApi.remove(p.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const removeCategory = async (c) => {
    if (!await confirm({
      title: 'حذف دسته',
      message: `دسته «${c.name}» حذف شود؟`,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    try {
      await productsApi.removeCategory(c.id)
      if (categoryFilter === String(c.id)) setCategoryFilter('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page products-page">
      <div className="products-page-header">
        <div>
          <h1 className="page-title">محصولات</h1>
          <p className="muted">مدیریت کاتالوگ، دسته‌بندی و رنگ‌بندی محصولات</p>
        </div>
        {canManage && (
          <div className="products-header-actions">
            <Button type="button" variant="ghost" onClick={openCreateCategory}>+ دسته</Button>
            <Button type="button" onClick={openCreateProduct}>+ محصول</Button>
          </div>
        )}
      </div>

      {error && <div className="alert-error">{error}</div>}

      {topSelling.length > 0 && (
        <Card title="پرفروش‌ترین کالاها" className="analytics-card">
          <p className="muted small" style={{ marginBottom: 12 }}>
            بر اساس تعداد فروخته‌شده در فاکتورهای قطعی
          </p>
          <div className="table-wrap">
            <table className="table table-compact">
              <thead>
                <tr>
                  <th>#</th>
                  <th>محصول</th>
                  <th>مدل</th>
                  <th>پارچه</th>
                  <th>تعداد فروش</th>
                  <th>تعداد فاکتور</th>
                  <th>مجموع درآمد</th>
                </tr>
              </thead>
              <tbody>
                {topSelling.map((item, idx) => (
                  <tr key={`${item.product_id || item.product_name}-${idx}`}>
                    <td>{idx + 1}</td>
                    <td>{item.product_name}</td>
                    <td>{item.product_model || '—'}</td>
                    <td>{item.fabric || '—'}</td>
                    <td><strong>{item.total_quantity}</strong></td>
                    <td>{item.sales_count}</td>
                    <td>{formatMoney(item.total_revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="category-scroll">
        <button
          type="button"
          className={`category-chip${!categoryFilter ? ' active' : ''}`}
          onClick={() => setCategoryFilter('')}
        >
          همه
        </button>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`category-chip${categoryFilter === String(c.id) ? ' active' : ''}`}
            style={{ '--cat-color': c.color }}
            onClick={() => setCategoryFilter(String(c.id))}
          >
            <span>{c.icon}</span> {c.name}
            <span className="category-count">{c.product_count}</span>
          </button>
        ))}
      </div>

      <Card>
        <FilterBar>
          <Field label="جستجو">
            <input
              className="search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="نام، کد، برند یا رنگ…"
            />
          </Field>
          <Field label="دسته">
            <Select value={categoryFilter} onChange={setCategoryFilter} options={categoryOptions} placeholder="همه" />
          </Field>
        </FilterBar>

        {loading ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : products.length === 0 ? (
          <EmptyState text="محصولی یافت نشد." />
        ) : (
          <div className="product-catalog-grid">
            {products.map((p) => (
              <article key={p.id} className={`product-card${p.is_active ? '' : ' inactive'}`}>
                <div className="product-card-head">
                  <div>
                    {p.category && (
                      <Badge color={p.category.color}>{p.category.icon} {p.category.name}</Badge>
                    )}
                    <h3>{p.name}</h3>
                    {p.product_model && <p className="muted small">مدل: {p.product_model}</p>}
                    {p.fabric && <p className="muted small">پارچه: {p.fabric}</p>}
                    {p.sku && <p className="muted small ltr">SKU: {p.sku}</p>}
                  </div>
                  {!p.is_active && <Badge color="#94a3b8">غیرفعال</Badge>}
                </div>

                {p.variants?.length > 0 && (
                  <div className="product-color-swatches">
                    {p.variants.map((v) => (
                      <span
                        key={v.id}
                        className="color-swatch"
                        title={v.color_name}
                        style={{ background: v.color_hex, borderColor: v.color_hex === '#f8fafc' ? '#cbd5e1' : v.color_hex }}
                      />
                    ))}
                  </div>
                )}

                <div className="product-card-meta">
                  <strong>{formatMoney(p.display_price)}</strong>
                  <span className="muted">{p.variants?.length || 0} رنگ</span>
                </div>

                {p.description && <p className="product-card-desc muted">{p.description}</p>}

                {canManage && (
                  <div className="product-card-actions">
                    <button type="button" className="link" onClick={() => openEditProduct(p)}>ویرایش</button>
                    <button type="button" className="link danger" onClick={() => removeProduct(p)}>حذف</button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </Card>

      {canManage && categories.length > 0 && (
        <Card title="دسته‌بندی‌ها">
          <div className="category-manage-list">
            {categories.map((c) => (
              <div key={c.id} className="category-manage-row">
                <span className="category-manage-icon" style={{ background: c.color }}>{c.icon}</span>
                <div className="category-manage-info">
                  <strong>{c.name}</strong>
                  <span className="muted">{c.product_count} محصول</span>
                </div>
                <div className="row-actions">
                  <button type="button" className="link" onClick={() => openEditCategory(c)}>ویرایش</button>
                  <button type="button" className="link danger" onClick={() => removeCategory(c)}>حذف</button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Modal
        title={editingProduct ? 'ویرایش محصول' : 'محصول جدید'}
        open={productModal}
        onClose={() => !saving && setProductModal(false)}
        wide
      >
        <form onSubmit={saveProduct} className="form product-form">
          <div className="form-grid-2">
            <Field label="نام محصول">
              <input value={productForm.name} onChange={(e) => setProductForm({ ...productForm, name: e.target.value })} required />
            </Field>
            <Field label="دسته">
              <Select
                value={productForm.category_id}
                onChange={(v) => setProductForm({ ...productForm, category_id: v })}
                options={[{ value: '', label: 'بدون دسته' }, ...categories.map((c) => ({ value: String(c.id), label: c.name }))]}
                placeholder="انتخاب دسته"
              />
            </Field>
            <Field label="کد محصول (SKU)">
              <input className="ltr" value={productForm.sku} onChange={(e) => setProductForm({ ...productForm, sku: e.target.value })} />
            </Field>
            <Field label="برند">
              <input value={productForm.brand} onChange={(e) => setProductForm({ ...productForm, brand: e.target.value })} />
            </Field>
            <Field label="مدل">
              <input value={productForm.product_model} onChange={(e) => setProductForm({ ...productForm, product_model: e.target.value })} placeholder="مثلاً کلاسیک" />
            </Field>
            <Field label="پارچه">
              <input value={productForm.fabric} onChange={(e) => setProductForm({ ...productForm, fabric: e.target.value })} placeholder="مثلاً مخمل، چرم" />
            </Field>
            <Field label="واحد">
              <input value={productForm.unit} onChange={(e) => setProductForm({ ...productForm, unit: e.target.value })} placeholder="عدد" />
            </Field>
            <Field label="قیمت (تومان)">
              <MoneyInput min="0" value={productForm.default_price} onChange={(e) => setProductForm({ ...productForm, default_price: e.target.value })} required />
            </Field>
          </div>

          <Field label="توضیحات">
            <textarea rows={2} value={productForm.description} onChange={(e) => setProductForm({ ...productForm, description: e.target.value })} />
          </Field>

          <div className="product-variants-section">
            <div className="section-head">
              <h4>رنگ‌بندی</h4>
              <Button type="button" variant="ghost" onClick={addVariant}>+ رنگ</Button>
            </div>
            {productForm.variants.map((v, idx) => (
              <div key={idx} className="variant-row">
                <div className="variant-color-presets">
                  {COLOR_PRESETS.map((preset) => (
                    <button
                      key={preset.hex}
                      type="button"
                      className="color-preset-btn"
                      title={preset.name}
                      style={{ background: preset.hex, borderColor: preset.hex === '#f8fafc' ? '#cbd5e1' : preset.hex }}
                      onClick={() => applyColorPreset(idx, preset)}
                    />
                  ))}
                </div>
                <div className="form-grid-2 variant-fields">
                  <Field label="نام رنگ">
                    <input value={v.color_name} onChange={(e) => updateVariant(idx, 'color_name', e.target.value)} placeholder="مثلاً مشکی" />
                  </Field>
                  <Field label="کد رنگ">
                    <input className="ltr" type="color" value={v.color_hex} onChange={(e) => updateVariant(idx, 'color_hex', e.target.value)} />
                  </Field>
                  <Field label="موجودی (اختیاری)">
                    <input className="ltr" type="number" min="0" value={v.stock} onChange={(e) => updateVariant(idx, 'stock', e.target.value)} placeholder="—" />
                  </Field>
                </div>
                {productForm.variants.length > 1 && (
                  <button type="button" className="link danger variant-remove" onClick={() => removeVariant(idx)}>حذف رنگ</button>
                )}
              </div>
            ))}
          </div>

          <label className="checkbox-row">
            <input type="checkbox" checked={productForm.is_active} onChange={(e) => setProductForm({ ...productForm, is_active: e.target.checked })} />
            فعال
          </label>

          <div className="form-actions">
            <Button type="button" variant="ghost" onClick={() => setProductModal(false)} disabled={saving}>انصراف</Button>
            <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره محصول'}</Button>
          </div>
        </form>
      </Modal>

      <Modal title={editingCategory ? 'ویرایش دسته' : 'دسته جدید'} open={categoryModal} onClose={() => !saving && setCategoryModal(false)}>
        <form onSubmit={saveCategory} className="form">
          <Field label="نام دسته">
            <input value={categoryForm.name} onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })} required />
          </Field>
          <Field label="آیکون">
            <input value={categoryForm.icon} onChange={(e) => setCategoryForm({ ...categoryForm, icon: e.target.value })} maxLength={8} />
          </Field>
          <Field label="رنگ">
            <input type="color" value={categoryForm.color} onChange={(e) => setCategoryForm({ ...categoryForm, color: e.target.value })} />
          </Field>
          <Field label="ترتیب">
            <input className="ltr" type="number" min="0" value={categoryForm.sort_order} onChange={(e) => setCategoryForm({ ...categoryForm, sort_order: e.target.value })} />
          </Field>
          <Field label="توضیحات">
            <textarea rows={2} value={categoryForm.description} onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })} />
          </Field>
          <label className="checkbox-row">
            <input type="checkbox" checked={categoryForm.is_active} onChange={(e) => setCategoryForm({ ...categoryForm, is_active: e.target.checked })} />
            فعال
          </label>
          <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره دسته'}</Button>
        </form>
      </Modal>
    </div>
  )
}
