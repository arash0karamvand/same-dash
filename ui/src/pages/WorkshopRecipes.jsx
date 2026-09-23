import { useCallback, useEffect, useMemo, useState } from 'react'
import { materialsApi, workshopRecipesApi } from '../api/client'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { parseRoute } from '../utils/routing'
import { hasAnyPermission } from '../utils/permissions'
import { formatMoney, formatNumber } from '../utils/format'
import { fromLegacy } from '../styles/tw.js'

const KIND_PAGES = {
  'factory-paint-recipes': { kind: 'paint', title: 'رنگ‌ها', usageKind: 'paint', nameLabel: 'نام رنگ' },
  'factory-fabric-recipes': { kind: 'fabric', title: 'پارچه‌ها', usageKind: 'fabric', nameLabel: 'نام کالیته' },
  'factory-foam-recipes': { kind: 'foam', title: 'اسفنج‌ها', usageKind: 'foam', nameLabel: 'نام اسفنج' },
  'factory-webbing-recipes': { kind: 'webbing', title: 'تسمه‌ها', usageKind: 'webbing', nameLabel: 'نام تسمه' },
  'factory-cushion-recipes': { kind: 'cushion', title: 'کوسن‌ها', usageKind: 'cushion', nameLabel: 'نام کوسن' },
}

const PAINT_CATEGORIES = [
  { value: 'thinner', label: 'تینر' },
  { value: 'paint', label: 'رنگ و پلی‌استر' },
  { value: 'putty', label: 'بتونه و سیلر' },
  { value: 'patina', label: 'پتینه و ورق طلا' },
  { value: 'abrasive', label: 'سنباده و ابزار مصرفی' },
  { value: 'chemical', label: 'هاردنر و شیمیایی' },
]

const PAINT_UNITS = ['لیتر', 'کیلوگرم', 'ورق', 'قوطی', 'گالن', 'حلب']

function swatchColor(name) {
  const text = name || 'پارچه'
  let hash = 0
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  return `hsl(${hash % 360} 38% 42%)`
}

function chipClass(active) {
  return `rounded-capsule border px-3 py-1.5 text-sm transition-colors ${
    active
      ? 'border-jelly-rim-strong bg-layer-3 text-text'
      : 'border-jelly-rim bg-layer-0 text-muted hover:bg-layer-2'
  }`
}

const EMPTY = {
  name: '',
  color_name: '',
  note: '',
  is_active: true,
  materials: [],
  item_code: '',
  paint_category: '',
  brand: '',
  stock_unit: '',
  current_stock: '',
  min_stock: '',
  storage_shelf: '',
  unit_cost: '',
  technical_specs: '',
  fabric_category: '',
  company_code: '',
  origin_country: '',
  fabric_country_id: '',
  fabric_brand_id: '',
  fabric_color_id: '',
  fabric_type_id: '',
  roll_count: '1',
}

export default function WorkshopRecipes() {
  const { page } = parseRoute()
  const meta = KIND_PAGES[page] || KIND_PAGES['factory-paint-recipes']
  const isPaint = meta.kind === 'paint'
  const isFabric = meta.kind === 'fabric'
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
  const [formError, setFormError] = useState('')
  const [categories, setCategories] = useState(PAINT_CATEGORIES)
  const [addingCategory, setAddingCategory] = useState(false)
  const [categoryName, setCategoryName] = useState('')
  const [categorySaving, setCategorySaving] = useState(false)
  const [catalog, setCatalog] = useState({ tree: [], brands: [], colors: [], types: [] })
  const [fabricPane, setFabricPane] = useState('stock')
  const [filterMode, setFilterMode] = useState('brand')
  const [filterId, setFilterId] = useState('')
  const [settingsCountry, setSettingsCountry] = useState('')
  const [settingsBrand, setSettingsBrand] = useState('')
  const [settingsColor, setSettingsColor] = useState('')
  const [nodeNames, setNodeNames] = useState({ country: '', brand: '', color: '', type: '' })
  const [nodeSaving, setNodeSaving] = useState(false)

  const categoryOptions = useMemo(() => {
    const options = [{ value: '', label: 'انتخاب…' }, ...categories]
    if (form.paint_category && !categories.some((item) => item.value === form.paint_category)) {
      options.push({ value: form.paint_category, label: form.paint_category })
    }
    return options
  }, [categories, form.paint_category])

  const fabricStats = useMemo(() => {
    const meters = recipes.reduce((sum, row) => sum + Number(row.current_stock || 0), 0)
    const companyIds = new Set(recipes.map((row) => row.fabric_brand_id).filter(Boolean))
    return {
      count: recipes.length,
      meters,
      companies: companyIds.size,
      low: recipes.filter((row) => row.stock_status === 'low').length,
    }
  }, [recipes])

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
      const filterKey = isFabric && filterId
        ? (filterMode === 'color' ? { color_id: filterId } : filterMode === 'type' ? { type_id: filterId } : { brand_id: filterId })
        : {}
      const [list, mats, cats, tree] = await Promise.all([
        workshopRecipesApi.list({
          kind: meta.kind,
          search: search.trim(),
          include_inactive: canManage ? '1' : undefined,
          limit: 200,
          ...filterKey,
        }),
        materialsApi.list({ limit: 300, approved_only: true, usage_kind: meta.usageKind }).catch(() => ({ results: [] })),
        isPaint ? workshopRecipesApi.paintCategories().catch(() => ({ results: null })) : Promise.resolve(null),
        isFabric ? workshopRecipesApi.fabricCatalog().catch(() => null) : Promise.resolve(null),
      ])
      setRecipes(list.results || [])
      setMaterials(mats.results || [])
      if (cats?.results) {
        setCategories(cats.results.map((item) => ({ value: item.code, label: item.label })))
      }
      if (tree?.tree) setCatalog(tree)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [isPaint, isFabric, meta.kind, meta.usageKind, search, canManage, filterMode, filterId])

  useEffect(() => { load() }, [load])

  const resetDrafts = () => {
    setAddingCategory(false)
    setCategoryName('')
    setFormError('')
  }

  const openCreate = () => {
    setEditing(null)
    setForm({ ...EMPTY, materials: [] })
    resetDrafts()
    setModalOpen(true)
  }

  const openEdit = (recipe) => {
    setEditing(recipe)
    setForm({
      name: recipe.name || '',
      color_name: recipe.color_name || '',
      note: recipe.note || '',
      is_active: recipe.is_active !== false,
      item_code: recipe.item_code || '',
      paint_category: recipe.paint_category || '',
      brand: recipe.brand || '',
      stock_unit: recipe.stock_unit || '',
      current_stock: recipe.current_stock ?? '',
      min_stock: recipe.min_stock ?? '',
      storage_shelf: recipe.storage_shelf || '',
      unit_cost: recipe.unit_cost ?? '',
      technical_specs: recipe.technical_specs || '',
      fabric_category: recipe.fabric_category || '',
      company_code: recipe.company_code || '',
      origin_country: recipe.origin_country || '',
      fabric_country_id: recipe.fabric_country_id ? String(recipe.fabric_country_id) : '',
      fabric_brand_id: recipe.fabric_brand_id ? String(recipe.fabric_brand_id) : '',
      fabric_color_id: recipe.fabric_color_id ? String(recipe.fabric_color_id) : '',
      fabric_type_id: recipe.fabric_type_id ? String(recipe.fabric_type_id) : '',
      roll_count: String(recipe.roll_count ?? 1),
      materials: (recipe.materials || []).map((row) => ({
        material_id: String(row.material_id),
        quantity: String(row.quantity ?? 1),
        unit: row.unit || '',
        normal_spoilage_rate: String(row.normal_spoilage_rate ?? 0),
      })),
    })
    resetDrafts()
    setModalOpen(true)
  }

  const createCategory = async () => {
    const label = categoryName.trim()
    if (!label) {
      setFormError('نام دسته‌بندی را وارد کنید.')
      return
    }
    setCategorySaving(true)
    setFormError('')
    try {
      const created = await workshopRecipesApi.createPaintCategory({ label })
      setCategories((prev) => (
        prev.some((item) => item.value === created.code)
          ? prev
          : [...prev, { value: created.code, label: created.label }]
      ))
      setForm((current) => ({ ...current, paint_category: created.code }))
      setAddingCategory(false)
      setCategoryName('')
    } catch (err) {
      setFormError(err.message)
    } finally {
      setCategorySaving(false)
    }
  }

  const countryNode = catalog.tree.find((item) => String(item.id) === form.fabric_country_id)
  const brandNode = (countryNode?.children || []).find((item) => String(item.id) === form.fabric_brand_id)
  const colorNode = (brandNode?.children || []).find((item) => String(item.id) === form.fabric_color_id)
  const brandChoices = countryNode?.children || []
  const colorChoices = brandNode?.children || []
  const typeChoices = colorNode?.children || []

  const settingsCountryNode = catalog.tree.find((item) => String(item.id) === settingsCountry)
  const settingsBrandNode = (settingsCountryNode?.children || []).find((item) => String(item.id) === settingsBrand)
  const settingsColorNode = (settingsBrandNode?.children || []).find((item) => String(item.id) === settingsColor)

  const pickNode = (kind) => {
    const label = (nodeNames[kind] || '').trim()
    if (!label) {
      setError('نام را وارد کنید.')
      return null
    }
    const parentId = kind === 'country' ? null
      : kind === 'brand' ? settingsCountry
        : kind === 'color' ? settingsBrand
          : settingsColor
    if (kind !== 'country' && !parentId) {
      setError('اول مورد بالادست را انتخاب کنید.')
      return null
    }
    return { kind, name: label, parent_id: parentId ? Number(parentId) : null }
  }

  const addCatalogNode = async (kind) => {
    const payload = pickNode(kind)
    if (!payload) return
    setNodeSaving(true)
    setError('')
    try {
      await workshopRecipesApi.createFabricCatalogNode(payload)
      setNodeNames((current) => ({ ...current, [kind]: '' }))
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setNodeSaving(false)
    }
  }

  const removeCatalogNode = async (node, label) => {
    if (!(await confirm({ title: 'حذف از تنظیمات', message: `${label} حذف شود؟` }))) return
    try {
      await workshopRecipesApi.removeFabricCatalogNode(node.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const updateRow = (idx, key, val) => {
    setForm((f) => ({
      ...f,
      materials: f.materials.map((row, i) => (i === idx ? { ...row, [key]: val } : row)),
    }))
  }

  const save = async () => {
    setSaving(true)
    setFormError('')
    try {
      const payload = {
        kind: meta.kind,
        name: form.name.trim(),
        color_name: form.color_name.trim(),
        note: form.note.trim(),
        is_active: form.is_active,
        ...(isPaint ? {
          item_code: form.item_code.trim(),
          paint_category: form.paint_category,
          brand: form.brand.trim(),
          stock_unit: form.stock_unit,
          current_stock: form.current_stock,
          min_stock: form.min_stock,
          storage_shelf: form.storage_shelf.trim(),
          unit_cost: form.unit_cost,
          technical_specs: form.technical_specs.trim(),
        } : {}),
        ...(isFabric ? {
          item_code: form.item_code.trim(),
          fabric_country_id: form.fabric_country_id ? Number(form.fabric_country_id) : null,
          fabric_brand_id: form.fabric_brand_id ? Number(form.fabric_brand_id) : null,
          fabric_color_id: form.fabric_color_id ? Number(form.fabric_color_id) : null,
          fabric_type_id: form.fabric_type_id ? Number(form.fabric_type_id) : null,
          current_stock: form.current_stock,
          min_stock: form.min_stock,
          unit_cost: form.unit_cost,
          roll_count: form.roll_count,
          technical_specs: form.technical_specs.trim(),
        } : {}),
        materials: form.materials
          .filter((row) => row.material_id)
          .map((row) => ({
            material_id: Number(row.material_id),
            quantity: Number(row.quantity) || 1,
            unit: row.unit || '',
            normal_spoilage_rate: Number(row.normal_spoilage_rate) || 0,
          })),
      }
      if (editing) await workshopRecipesApi.update(editing.id, payload)
      else await workshopRecipesApi.create(payload)
      setModalOpen(false)
      setEditing(null)
      await load()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const removeRecipe = async (recipe) => {
    const title = isFabric ? 'حذف کالیته' : 'حذف دستور'
    if (!(await confirm({ title, message: `${recipe.name} حذف شود؟` }))) return
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
          <h1>{isFabric ? 'کاتالوگ پارچه' : `کاتالوگ ${meta.title}`}</h1>
          <p className={fromLegacy('muted')}>
            {isFabric
              ? 'کالیته و طاقه: شرکت، جنس، کشور، متراژ و قیمت هر متر'
              : 'دستور دست‌کار برای محصول — بدون رکورد نمونه؛ فقط تعریف قابلیت'}
          </p>
        </div>
        {canManage && <Button onClick={openCreate}>{isFabric ? '+ ثبت کالیته' : '+ دستور جدید'}</Button>}
      </div>

      {error && <div className={fromLegacy('alert error')}>{error}</div>}

      {isFabric && (
        <div className={fromLegacy('stat-grid')}>
          <StatCard label="کالیته‌ها" value={formatNumber(fabricStats.count)} />
          <StatCard label="مجموع متراژ" value={formatNumber(fabricStats.meters)} hint="متر" />
          <StatCard label="برندها" value={formatNumber(fabricStats.companies)} />
          <StatCard label="نزدیک اتمام" value={formatNumber(fabricStats.low)} accent="var(--warning)" />
        </div>
      )}

      {isFabric && (
        <div className={fromLegacy('workflow-filter-tabs')}>
          <button type="button" className={fromLegacy(`workflow-filter-tab ${fabricPane === 'stock' ? 'active' : ''}`)} onClick={() => setFabricPane('stock')}>کالیته‌ها</button>
          <button type="button" className={fromLegacy(`workflow-filter-tab ${fabricPane === 'settings' ? 'active' : ''}`)} onClick={() => setFabricPane('settings')}>تنظیمات</button>
        </div>
      )}

      {isFabric && fabricPane === 'settings' ? (
        <Card>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
            {[
              { title: 'کشور', kind: 'country', items: catalog.tree, selected: settingsCountry, onSelect: (id) => { setSettingsCountry(id); setSettingsBrand(''); setSettingsColor('') } },
              { title: 'برند', kind: 'brand', items: settingsCountryNode?.children || [], selected: settingsBrand, onSelect: (id) => { setSettingsBrand(id); setSettingsColor('') } },
              { title: 'رنگ', kind: 'color', items: settingsBrandNode?.children || [], selected: settingsColor, onSelect: setSettingsColor },
              { title: 'جنس', kind: 'type', items: settingsColorNode?.children || [], selected: '', onSelect: () => {} },
            ].map((column) => (
              <div key={column.kind} className="flex flex-col gap-2 rounded-pill border border-jelly-rim bg-layer-1 p-3">
                <h4 className="m-0 text-sm font-semibold">{column.title}</h4>
                <div className="flex max-h-56 flex-col gap-1 overflow-auto">
                  {column.items.length === 0 ? (
                    <p className={fromLegacy('muted small')}>موردی نیست.</p>
                  ) : column.items.map((item) => (
                    <div key={item.id} className="flex items-center gap-1">
                      <button
                        type="button"
                        className={`${chipClass(String(item.id) === column.selected)} min-w-0 flex-1 text-right`}
                        onClick={() => column.onSelect(String(item.id))}
                      >
                        {item.name}
                      </button>
                      {canManage && (
                        <Button type="button" variant="ghost" size="sm" onClick={() => removeCatalogNode(item, item.name)}>حذف</Button>
                      )}
                    </div>
                  ))}
                </div>
                {canManage && (
                  <div className="mt-auto flex flex-col gap-2">
                    <input value={nodeNames[column.kind] || ''} onChange={(e) => setNodeNames((current) => ({ ...current, [column.kind]: e.target.value }))} placeholder={`نام ${column.title}`} />
                    <Button type="button" disabled={nodeSaving} onClick={() => addCatalogNode(column.kind)}>افزودن {column.title}</Button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      ) : (
      <>
      <FilterBar>
        <Field label="جستجو">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={isFabric ? 'نام، رنگ، کد، شرکت یا دسته…' : isPaint ? 'نام، فام، کد یا برند…' : 'نام یا فام…'}
          />
        </Field>
        {isFabric && (
          <>
            <Field label="فیلتر بر اساس">
              <Select
                value={filterMode}
                onChange={(value) => { setFilterMode(value); setFilterId('') }}
                options={[
                  { value: 'brand', label: 'برندهای موجود' },
                  { value: 'color', label: 'همه رنگ‌ها' },
                  { value: 'type', label: 'جنس‌ها' },
                ]}
              />
            </Field>
            <Field label={filterMode === 'color' ? 'رنگ' : filterMode === 'type' ? 'جنس' : 'برند'}>
              <Select
                value={filterId}
                onChange={setFilterId}
                options={[
                  { value: '', label: 'همه' },
                  ...(filterMode === 'color' ? catalog.colors : filterMode === 'type' ? catalog.types : catalog.brands).map((item) => ({
                    value: String(item.id),
                    label: filterMode === 'brand'
                      ? item.name
                      : filterMode === 'color'
                        ? `${item.name} · ${item.brand_name}`
                        : `${item.name} · ${item.color_name}`,
                  })),
                ]}
              />
            </Field>
          </>
        )}
      </FilterBar>

      {loading ? (
        <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
      ) : recipes.length === 0 ? (
        <EmptyState text={isFabric ? 'کالیته‌ای با این فیلتر نیست. با «ثبت کالیته» طاقه را وارد کاتالوگ کنید.' : 'دستوری تعریف نشده.'} />
      ) : isFabric ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(16.5rem,1fr))] gap-4">
          {recipes.map((recipe) => {
            const tone = swatchColor(recipe.color_name || recipe.name)
            return (
              <article key={recipe.id} className="flex overflow-hidden rounded-pill border border-jelly-rim bg-layer-2 shadow-jelly">
                <div className="w-2 shrink-0" style={{ background: tone }} />
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="h-2" style={{ background: tone }} />
                  <div className="flex flex-1 flex-col gap-2 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <strong className="min-w-0">{recipe.name}</strong>
                      {!recipe.is_active && <Badge>غیرفعال</Badge>}
                      {recipe.stock_status === 'zero' && <Badge color="var(--danger)">موجودی صفر</Badge>}
                      {recipe.stock_status === 'low' && <Badge color="var(--warning)">نزدیک اتمام</Badge>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {recipe.company_display && <span className={chipClass(true)}>{recipe.company_display}</span>}
                      {recipe.fabric_type_name && <span className={chipClass(false)}>{recipe.fabric_type_name}</span>}
                    </div>
                    <p className={fromLegacy('muted small')}>
                      {[recipe.item_code, recipe.color_name, recipe.origin_country].filter(Boolean).join(' · ') || 'بدون کد'}
                    </p>
                    <div className="mt-auto grid grid-cols-3 gap-2 rounded-capsule bg-layer-1 px-3 py-2 text-sm">
                      <div>
                        <div className={fromLegacy('muted small')}>متراژ</div>
                        <div>{formatNumber(recipe.current_stock)}</div>
                      </div>
                      <div>
                        <div className={fromLegacy('muted small')}>طاقه</div>
                        <div>{formatNumber(recipe.roll_count)}</div>
                      </div>
                      <div>
                        <div className={fromLegacy('muted small')}>هر متر</div>
                        <div>{formatMoney(recipe.unit_cost)}</div>
                      </div>
                    </div>
                    {canManage && (
                      <div className={fromLegacy('row')}>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(recipe)}>ویرایش</Button>
                        <Button variant="ghost" size="sm" onClick={() => removeRecipe(recipe)}>حذف</Button>
                      </div>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      ) : (
        <Card>
          {recipes.map((recipe) => (
            <div key={recipe.id} className={fromLegacy('frame-row')}>
              <div>
                <strong>{recipe.name}</strong>
                {!recipe.is_active && <Badge>غیرفعال</Badge>}
                {isPaint && recipe.stock_status === 'zero' && <Badge color="var(--danger)">موجودی صفر</Badge>}
                {isPaint && recipe.stock_status === 'low' && <Badge color="var(--warning)">کسری</Badge>}
                <div className={fromLegacy('muted small')}>
                  {recipe.color_name || 'بدون فام'}
                  {(recipe.materials || []).length > 0 && ` • ${(recipe.materials || []).length} متریال`}
                </div>
                {isPaint && (
                  <div className={fromLegacy('muted small')}>
                    {[recipe.item_code, recipe.paint_category_display, recipe.brand, recipe.storage_shelf].filter(Boolean).join(' • ') || 'بدون کد'}
                    {' • '}
                    موجودی {formatNumber(recipe.current_stock)} {recipe.stock_unit}
                    {' • '}
                    نرخ {formatMoney(recipe.unit_cost)}
                    {' • '}
                    ارزش {formatMoney(recipe.stock_value)}
                  </div>
                )}
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
      </>
      )}

      <Modal
        wide
        title={editing ? `ویرایش ${editing.name}` : (isFabric ? 'ثبت کالیته و طاقه' : `دستور ${meta.title}`)}
        open={modalOpen}
        onClose={() => { setModalOpen(false); resetDrafts() }}
      >
        <div className={fromLegacy('form')}>
          {formError && <div className={fromLegacy('alert error')}>{formError}</div>}

          <section className="flex flex-col gap-3">
            <div className={fromLegacy('section-head')}>
              <h4>مشخصات</h4>
            </div>
            <div className={fromLegacy('form-grid-2')}>
              <Field label={meta.nameLabel}>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </Field>
              {!isFabric && (
                <Field label="رنگ / فام">
                  <input value={form.color_name} onChange={(e) => setForm({ ...form, color_name: e.target.value })} />
                </Field>
              )}
              {isPaint && (
                <>
                  <Field label="کد رهگیری">
                    <input
                      value={form.item_code}
                      onChange={(e) => setForm({ ...form, item_code: e.target.value })}
                      placeholder="خالی بماند تا کد ساخته شود"
                    />
                  </Field>
                  <Field label="برند">
                    <input value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} />
                  </Field>
                  <div className="col-span-2 flex flex-col gap-2 max-bp900:col-span-1">
                    <div className="flex items-end gap-2">
                      <div className="min-w-0 flex-1">
                        <Field label="دسته‌بندی">
                          <Select
                            value={form.paint_category}
                            onChange={(v) => setForm({ ...form, paint_category: v })}
                            options={categoryOptions}
                          />
                        </Field>
                      </div>
                      {canManage && (
                        <Button type="button" variant="ghost" onClick={() => setAddingCategory((open) => !open)}>
                          {addingCategory ? 'بستن' : 'ساخت دسته‌بندی'}
                        </Button>
                      )}
                    </div>
                    {addingCategory && (
                      <div className="flex flex-wrap items-center gap-2 rounded-capsule border border-jelly-rim bg-layer-1 p-3">
                        <input
                          className="min-w-[12rem] flex-1"
                          value={categoryName}
                          onChange={(e) => setCategoryName(e.target.value)}
                          placeholder="نام دسته‌بندی"
                        />
                        <Button type="button" disabled={categorySaving} onClick={createCategory}>
                          {categorySaving ? 'در حال ثبت…' : 'ثبت دسته'}
                        </Button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            {isFabric && (
              <div className={`${fromLegacy('form-grid-2')} rounded-pill border border-jelly-rim bg-layer-1 p-4`}>
                <Field label="کشور سازنده">
                  <Select
                    value={form.fabric_country_id}
                    onChange={(value) => setForm({ ...form, fabric_country_id: value, fabric_brand_id: '', fabric_color_id: '', fabric_type_id: '' })}
                    options={[{ value: '', label: 'انتخاب کشور…' }, ...catalog.tree.map((item) => ({ value: String(item.id), label: item.name }))]}
                  />
                </Field>
                <Field label="برند">
                  <Select
                    value={form.fabric_brand_id}
                    onChange={(value) => setForm({ ...form, fabric_brand_id: value, fabric_color_id: '', fabric_type_id: '' })}
                    options={[{ value: '', label: form.fabric_country_id ? 'انتخاب برند…' : 'اول کشور را انتخاب کنید' }, ...brandChoices.map((item) => ({ value: String(item.id), label: item.name }))]}
                  />
                </Field>
                <Field label="رنگ">
                  <Select
                    value={form.fabric_color_id}
                    onChange={(value) => setForm({ ...form, fabric_color_id: value, fabric_type_id: '' })}
                    options={[{ value: '', label: form.fabric_brand_id ? 'انتخاب رنگ…' : 'اول برند را انتخاب کنید' }, ...colorChoices.map((item) => ({ value: String(item.id), label: item.name }))]}
                  />
                </Field>
                <Field label="جنس پارچه">
                  <Select
                    value={form.fabric_type_id}
                    onChange={(value) => setForm({ ...form, fabric_type_id: value })}
                    options={[{ value: '', label: form.fabric_color_id ? 'انتخاب جنس…' : 'اول رنگ را انتخاب کنید' }, ...typeChoices.map((item) => ({ value: String(item.id), label: item.name }))]}
                  />
                </Field>
              </div>
            )}
          </section>

          {isFabric && (
            <section className="flex flex-col gap-3">
              <div className={fromLegacy('section-head')}>
                <h4>جنس و موجودی</h4>
              </div>
              <Field label="کد کالیته">
                <input
                  value={form.item_code}
                  onChange={(e) => setForm({ ...form, item_code: e.target.value })}
                  placeholder="خالی بماند تا کد ساخته شود"
                />
              </Field>
              <div className="grid grid-cols-2 gap-4 rounded-pill border border-jelly-rim bg-layer-0 p-4 max-bp900:grid-cols-1">
                <Field label="متراژ (متر)">
                  <input className={fromLegacy('ltr')} type="number" min="0" step="0.001" value={form.current_stock} onChange={(e) => setForm({ ...form, current_stock: e.target.value })} />
                </Field>
                <Field label="تعداد طاقه">
                  <input className={fromLegacy('ltr')} type="number" min="0" step="1" value={form.roll_count} onChange={(e) => setForm({ ...form, roll_count: e.target.value })} />
                </Field>
                <Field label="حداقل هشدار (متر)">
                  <input className={fromLegacy('ltr')} type="number" min="0" step="0.001" value={form.min_stock} onChange={(e) => setForm({ ...form, min_stock: e.target.value })} />
                </Field>
                <Field label="قیمت هر متر">
                  <MoneyInput value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} />
                </Field>
              </div>
            </section>
          )}

          {isPaint && (
            <section className="flex flex-col gap-3">
              <div className={fromLegacy('section-head')}>
                <h4>موجودی و نرخ</h4>
              </div>
              <div className={fromLegacy('form-grid-2')}>
                <Field label="واحد شمارش">
                  <Select
                    value={form.stock_unit}
                    onChange={(v) => setForm({ ...form, stock_unit: v })}
                    options={[{ value: '', label: 'انتخاب…' }, ...PAINT_UNITS.map((unit) => ({ value: unit, label: unit }))]}
                  />
                </Field>
                <Field label="موقعیت قفسه">
                  <input value={form.storage_shelf} onChange={(e) => setForm({ ...form, storage_shelf: e.target.value })} />
                </Field>
                <Field label="موجودی">
                  <input
                    className={fromLegacy('ltr')}
                    type="number"
                    min="0"
                    step="0.001"
                    value={form.current_stock}
                    onChange={(e) => setForm({ ...form, current_stock: e.target.value })}
                  />
                </Field>
                <Field label="نقطه سفارش">
                  <input
                    className={fromLegacy('ltr')}
                    type="number"
                    min="0"
                    step="0.001"
                    value={form.min_stock}
                    onChange={(e) => setForm({ ...form, min_stock: e.target.value })}
                  />
                </Field>
                <div className="col-span-2 max-bp900:col-span-1">
                  <Field label="نرخ واحد">
                    <MoneyInput value={form.unit_cost} onChange={(e) => setForm({ ...form, unit_cost: e.target.value })} />
                  </Field>
                </div>
              </div>
            </section>
          )}

          <section className="flex flex-col gap-3">
            <div className={fromLegacy('section-head')}>
              <h4>{isPaint || isFabric ? 'یادداشت' : 'توضیحات'}</h4>
            </div>
            {isFabric && (
              <Field label="مشخصات فنی">
                  <textarea
                    rows={2}
                    value={form.technical_specs}
                    onChange={(e) => setForm({ ...form, technical_specs: e.target.value })}
                    placeholder="عرض، گرماژ، شستشو یا خواب پارچه"
                  />
              </Field>
            )}
            {isPaint && (
              <Field label="مشخصات فنی">
                <textarea
                  rows={2}
                  value={form.technical_specs}
                  onChange={(e) => setForm({ ...form, technical_specs: e.target.value })}
                  placeholder="نسبت اختلاط، ویسکوزیته یا نکته ایمنی"
                />
              </Field>
            )}
            <Field label="توضیحات">
              <textarea rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
            </Field>
          </section>

          <section className="flex flex-col gap-3">
            <div className={fromLegacy('section-head')}>
              <h4>متریال مصرفی</h4>
              {canManage && (
                <Button type="button" variant="ghost" size="sm" onClick={() => setForm({ ...form, materials: [...form.materials, { material_id: '', quantity: '1', unit: '', normal_spoilage_rate: '0' }] })}>+ متریال</Button>
              )}
            </div>
            {form.materials.length === 0 ? (
              <p className={fromLegacy('muted small')}>متریالی اضافه نشده.</p>
            ) : form.materials.map((row, idx) => (
              <div key={idx} className="grid grid-cols-1 items-end gap-3 rounded-capsule border border-jelly-rim bg-layer-1 p-3 sm:grid-cols-[1fr_8rem_auto]">
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
                <Field label="ضایعات عادی ٪">
                  <input className={fromLegacy('ltr')} type="number" min="0" max="100" step="0.01" value={row.normal_spoilage_rate ?? 0} onChange={(e) => updateRow(idx, 'normal_spoilage_rate', e.target.value)} />
                </Field>
                <Button type="button" variant="ghost" size="sm" onClick={() => setForm({ ...form, materials: form.materials.filter((_, i) => i !== idx) })}>حذف</Button>
              </div>
            ))}
          </section>

          <div className={`${fromLegacy('form-actions')} border-t border-border-subtle pt-3`}>
            <label className={fromLegacy('checkbox-row')}>
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              فعال
            </label>
            <Button disabled={saving} onClick={save}>{saving ? 'در حال ذخیره…' : 'ذخیره'}</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
