import { useCallback, useEffect, useMemo, useState } from 'react'
import { configApi, furnitureWorksetsApi, materialsApi, productsApi, workshopRecipesApi } from '../api/client'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal } from '../components/ui'
import { PAGE_SIZE, PICKER_LIMIT } from '../config/pagination'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatMoney } from '../utils/format'
import { parseRoute } from '../utils/routing'
import { fromLegacy } from '../styles/tw.js'

import { canSeePortal, hasAnyPermission, hasPermission } from '../utils/permissions'
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

const EMPTY_CATEGORY = { name: '', description: '', color: 'var(--accent)', icon: 'package', sort_order: 0, is_active: true }
const EMPTY_VARIANT = { color_name: '', color_hex: '#cccccc', sku: '', stock_by_location: [], is_active: true }

function locationStocksFrom(locations, existing = []) {
  const byKey = new Map((existing || []).map((row) => [row.key, row]))
  return (locations || []).map((loc) => {
    const current = byKey.get(loc.key)
    const qty = current?.quantity
    return {
      key: loc.key,
      kind: loc.kind,
      warehouse_id: loc.warehouse_id,
      branch: loc.branch || '',
      label: loc.label,
      quantity: qty === 0 || qty ? String(qty) : '',
    }
  })
}
const EMPTY_PRODUCT_MATERIAL = { id: null, material_id: '', quantity: '1', normal_spoilage_rate: '0' }
const EMPTY_SUITE_PIECE = {
  piece_kind: '',
  arm_style: '',
  piece_label: '',
  quantity: 1,
  needs_paint: true,
  pipeline_end: 'upholstery',
  paint_recipe_id: '',
  fabric_recipe_id: '',
  foam_recipe_id: '',
  webbing_recipe_id: '',
  cushion_recipe_id: '',
  unit_price: '',
}
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
  target_margin_percent: '',
  is_active: true,
  attributes: {},
  variants: [{ ...EMPTY_VARIANT }],
  materials: [],
  workset_id: '',
  suite_pieces: [],
}

function piecesFromWorkset(workset, existing = []) {
  const prev = new Map((existing || []).map((piece) => [`${piece.piece_kind}:${piece.arm_style}`, piece]))
  return (workset?.pieces || []).map((piece) => {
    const old = prev.get(`${piece.piece_kind}:${piece.arm_style}`) || {}
    const assembly = piece.piece_kind === 'side_table' || piece.piece_kind === 'coffee_table'
    return {
      ...EMPTY_SUITE_PIECE,
      piece_kind: piece.piece_kind,
      arm_style: piece.arm_style,
      piece_label: piece.piece_label || old.piece_label || '',
      quantity: piece.quantity || old.quantity || 1,
      needs_paint: old.needs_paint !== false,
      pipeline_end: old.pipeline_end || (assembly ? 'assembly' : 'upholstery'),
      paint_recipe_id: old.paint_recipe_id ? String(old.paint_recipe_id) : '',
      fabric_recipe_id: old.fabric_recipe_id ? String(old.fabric_recipe_id) : '',
      foam_recipe_id: old.foam_recipe_id ? String(old.foam_recipe_id) : '',
      webbing_recipe_id: old.webbing_recipe_id ? String(old.webbing_recipe_id) : '',
      cushion_recipe_id: old.cushion_recipe_id ? String(old.cushion_recipe_id) : '',
      unit_price: old.unit_price != null && old.unit_price !== '' ? String(old.unit_price) : '',
    }
  })
}

function suiteTotal(pieces) {
  return (pieces || []).reduce((sum, piece) => sum + (Number(piece.unit_price) || 0) * (Number(piece.quantity) || 1), 0)
}

function useProductMode() {
  const { portal } = parseRoute()
  if (portal === 'factory') return 'factory'
  if (portal === 'office') return 'office'
  return 'sales'
}

export default function Products() {
  const { user } = useAuth()
  const { stockLocations, inventorySettings, portals, refresh } = useConfig()
  const confirm = useConfirm()
  const mode = useProductMode()
  const isFactory = mode === 'factory'
  const isOffice = mode === 'office'
  const canManage = hasAnyPermission(user, ['manage_products', 'manage_factory_products'])
  const canManageSales = hasPermission(user, 'manage_products')
  const canManageFactory = hasPermission(user, 'manage_factory_products')
  const canDelete = canManageSales
  const showSalesPrice = !isFactory
  const showCosts = isOffice || (hasPermission(user, 'view_materials') && hasPermission(user, 'view_products'))
  const canEditMaterials = canManageFactory
  const canManageCategories = canManageSales || canManageFactory
  const managersPortal = (portals || []).find((portal) => portal.id === 'managers')
  const canLockManualStock = canSeePortal(user, managersPortal)
  const manualStockLocked = Boolean(inventorySettings?.manual_stock_locked)

  const productsGuideText = isFactory
    ? PAGE_GUIDE_DEFAULTS.products_factory
    : isOffice
      ? PAGE_GUIDE_DEFAULTS.products_office
      : PAGE_GUIDE_DEFAULTS.products_shop
  useRegisterPageGuide('products', productsGuideText)

  const [categories, setCategories] = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)

  const [productModal, setProductModal] = useState(false)
  const [categoryModal, setCategoryModal] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [editingCategory, setEditingCategory] = useState(null)
  const [productForm, setProductForm] = useState(EMPTY_PRODUCT)
  const [categoryForm, setCategoryForm] = useState(EMPTY_CATEGORY)
  const [saving, setSaving] = useState(false)
  const [topSelling, setTopSelling] = useState([])
  const [materialCatalog, setMaterialCatalog] = useState([])
  const [worksetCatalog, setWorksetCatalog] = useState([])
  const [recipeCatalog, setRecipeCatalog] = useState({ paint: [], fabric: [], foam: [], cushion: [], webbing: [] })
  const [transferOpen, setTransferOpen] = useState(false)
  const [transferForm, setTransferForm] = useState({
    variant_id: '',
    source: '',
    destination: '',
    quantity: '',
  })
  const [transferBusy, setTransferBusy] = useState(false)
  const [lockBusy, setLockBusy] = useState(false)

  const load = useCallback(async ({ append = false, offset: nextOffset = 0 } = {}) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
    try {
      const productReq = productsApi.list({
        search: search.trim(),
        category_id: categoryFilter || undefined,
        offset: nextOffset,
        limit: PAGE_SIZE,
        include_inactive: canManage,
        is_active: canManage ? (activeFilter || undefined) : undefined,
      })
      if (append) {
        const data = await productReq
        setProducts((prev) => [...prev, ...(data.results || [])])
        setTotal(data.total || 0)
        setOffset(data.offset ?? nextOffset)
        setError('')
        return
      }
      const loadTopSelling = mode === 'sales' && hasPermission(user, 'view_products')
      const loadMaterials = showCosts || canEditMaterials
      const requests = [
        productsApi.categories({ active: canManage ? undefined : true }),
        productReq,
      ]
      if (loadTopSelling) {
        requests.push(productsApi.topSelling(20).catch(() => ({ results: [] })))
      }
      if (loadMaterials) {
        requests.push(materialsApi.list({ limit: PICKER_LIMIT, approved_only: true }).catch(() => ({ results: [] })))
      }
      const loadWorkset = isFactory || canEditMaterials
      if (loadWorkset) {
        requests.push(workshopRecipesApi.list({ limit: 400 }).catch(() => ({ results: [] })))
        requests.push(furnitureWorksetsApi.list({ limit: 200 }).catch(() => ({ results: [] })))
      }
      const results = await Promise.all(requests)
      let i = 0
      setCategories(results[i].results || [])
      i += 1
      const productData = results[i]
      setProducts(productData.results || [])
      setTotal(productData.total || 0)
      setOffset(productData.offset ?? 0)
      i += 1
      if (loadTopSelling) {
        setTopSelling(results[i]?.results || [])
        i += 1
      } else {
        setTopSelling([])
      }
      if (loadMaterials) {
        setMaterialCatalog(results[i]?.results || [])
        i += 1
      }
      if (loadWorkset) {
        const recipes = results[i]?.results || []
        setRecipeCatalog({
          paint: recipes.filter((r) => r.kind === 'paint'),
          fabric: recipes.filter((r) => r.kind === 'fabric'),
          foam: recipes.filter((r) => r.kind === 'foam'),
          cushion: recipes.filter((r) => r.kind === 'cushion'),
          webbing: recipes.filter((r) => r.kind === 'webbing'),
        })
        i += 1
        setWorksetCatalog(results[i]?.results || [])
      }
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [search, categoryFilter, activeFilter, canManage, mode, showCosts, canEditMaterials, isFactory, user])

  useEffect(() => { load() }, [load])

  const categoryOptions = useMemo(
    () => [{ value: '', label: 'همه دسته‌ها' }, ...categories.map((c) => ({ value: String(c.id), label: c.name }))],
    [categories],
  )

  const materialOptions = useMemo(
    () => materialCatalog.map((m) => ({
      value: String(m.id),
      label: m.color_name ? `${m.name} (${m.color_name})` : m.name,
    })),
    [materialCatalog],
  )

  const worksetOptions = useMemo(
    () => [{ value: '', label: 'بدون دست' }, ...worksetCatalog.map((w) => ({ value: String(w.id), label: w.name }))],
    [worksetCatalog],
  )

  const recipeOptions = (kind) => [
    { value: '', label: 'بدون دستور' },
    ...(recipeCatalog[kind] || []).map((r) => ({
      value: String(r.id),
      label: r.color_name ? `${r.name} (${r.color_name})` : r.name,
    })),
  ]

  const selectedRecipePreview = (kind, recipeId) => {
    const recipe = (recipeCatalog[kind] || []).find((r) => String(r.id) === String(recipeId))
    if (!recipe?.materials?.length) return null
    return recipe.materials.map((row) => `${row.material_name} × ${row.quantity} ${row.unit || ''}`).join('، ')
  }

  const onWorksetChange = async (value) => {
    let workset = worksetCatalog.find((row) => String(row.id) === String(value))
    if (value && workset && !(workset.pieces || []).length) {
      try {
        workset = await furnitureWorksetsApi.get(value)
      } catch {
        workset = workset || { pieces: [] }
      }
    }
    setProductForm((form) => ({
      ...form,
      workset_id: value,
      product_model: form.product_model || workset?.name || '',
      suite_pieces: piecesFromWorkset(workset, form.suite_pieces),
    }))
  }

  const updateSuitePiece = (idx, key, val) => {
    setProductForm((form) => ({
      ...form,
      suite_pieces: form.suite_pieces.map((piece, i) => (i === idx ? { ...piece, [key]: val } : piece)),
    }))
  }

  const openCreateProduct = () => {
    setEditingProduct(null)
    setProductForm({
      ...EMPTY_PRODUCT,
      variants: [{ ...EMPTY_VARIANT, stock_by_location: locationStocksFrom(stockLocations) }],
      materials: [],
    })
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
      target_margin_percent: p.target_margin_percent != null ? String(p.target_margin_percent) : '',
      is_active: p.is_active,
      attributes: { ...(p.attributes || {}) },
      variants: (p.variants?.length ? p.variants : [{ ...EMPTY_VARIANT }]).map((v) => ({
        id: v.id,
        color_name: v.color_name,
        color_hex: v.color_hex,
        sku: v.sku || '',
        stock_by_location: locationStocksFrom(stockLocations, v.stock_by_location),
        is_active: v.is_active !== false,
      })),
      materials: (p.materials || []).map((pm) => ({
        id: pm.id,
        material_id: String(pm.material_id),
        quantity: String(pm.quantity ?? 1),
        normal_spoilage_rate: String(pm.normal_spoilage_rate ?? 0),
      })),
      workset_id: p.furniture_workset_id ? String(p.furniture_workset_id) : '',
      suite_pieces: piecesFromWorkset(
        worksetCatalog.find((w) => String(w.id) === String(p.furniture_workset_id)) || { pieces: p.suite_config },
        p.suite_config || [],
      ),
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
      color: c.color || 'var(--accent)',
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
    setProductForm((f) => ({
      ...f,
      variants: [...f.variants, { ...EMPTY_VARIANT, stock_by_location: locationStocksFrom(stockLocations) }],
    }))
  }

  const updateVariantStock = (idx, key, quantity) => {
    setProductForm((f) => ({
      ...f,
      variants: f.variants.map((v, i) => (
        i === idx
          ? {
              ...v,
              stock_by_location: (v.stock_by_location || []).map((row) => (
                row.key === key ? { ...row, quantity } : row
              )),
            }
          : v
      )),
    }))
  }

  const removeVariant = (idx) => {
    setProductForm((f) => ({
      ...f,
      variants: f.variants.length > 1 ? f.variants.filter((_, i) => i !== idx) : f.variants,
    }))
  }

  const updateProductMaterial = (idx, key, val) => {
    setProductForm((f) => ({
      ...f,
      materials: f.materials.map((m, i) => (i === idx ? { ...m, [key]: val } : m)),
    }))
  }

  const addProductMaterial = () => {
    setProductForm((f) => ({ ...f, materials: [...f.materials, { ...EMPTY_PRODUCT_MATERIAL }] }))
  }

  const removeProductMaterial = (idx) => {
    setProductForm((f) => ({
      ...f,
      materials: f.materials.filter((_, i) => i !== idx),
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
        fabric: (() => {
          const fromSuite = (productForm.suite_pieces || []).find((piece) => piece.fabric_recipe_id)
          if (fromSuite?.fabric_recipe_id) {
            const recipe = (recipeCatalog.fabric || []).find((row) => String(row.id) === String(fromSuite.fabric_recipe_id))
            if (recipe?.name) return recipe.name
          }
          return productForm.fabric.trim()
        })(),
        description: productForm.description.trim(),
        unit: productForm.unit.trim() || 'عدد',
        category_id: productForm.category_id ? Number(productForm.category_id) : null,
        is_active: productForm.is_active,
        attributes: productForm.attributes,
        variants: productForm.variants
          .filter((v) => v.color_name.trim())
          .map((v) => ({
            id: v.id,
            color_name: v.color_name.trim(),
            color_hex: v.color_hex,
            sku: v.sku.trim(),
            stock_by_location: (v.stock_by_location || [])
              .filter((row) => row.quantity !== '' && row.quantity != null)
              .map((row) => ({
                kind: row.kind,
                warehouse_id: row.warehouse_id,
                branch: row.branch,
                quantity: Number(row.quantity),
              })),
            is_active: v.is_active !== false,
          })),
      }
      if (canManageSales) {
        payload.default_price = Number(productForm.default_price) || 0
        payload.target_margin_percent = productForm.target_margin_percent === '' ? null : Number(productForm.target_margin_percent)
      }
      if (canEditMaterials) {
        payload.materials = productForm.materials
          .filter((m) => m.material_id)
          .map((m) => ({
            id: m.id,
            material_id: Number(m.material_id),
            quantity: Number(m.quantity) || 1,
            normal_spoilage_rate: Number(m.normal_spoilage_rate) || 0,
          }))
        payload.furniture_workset_id = productForm.workset_id ? Number(productForm.workset_id) : null
        payload.suite_config = (productForm.suite_pieces || []).map((piece) => ({
          piece_kind: piece.piece_kind,
          arm_style: piece.arm_style,
          quantity: Number(piece.quantity) || 1,
          needs_paint: piece.needs_paint !== false,
          pipeline_end: piece.pipeline_end || 'upholstery',
          paint_recipe_id: piece.needs_paint && piece.paint_recipe_id ? Number(piece.paint_recipe_id) : null,
          fabric_recipe_id: piece.fabric_recipe_id ? Number(piece.fabric_recipe_id) : null,
          foam_recipe_id: piece.foam_recipe_id ? Number(piece.foam_recipe_id) : null,
          webbing_recipe_id: piece.webbing_recipe_id ? Number(piece.webbing_recipe_id) : null,
          cushion_recipe_id: piece.cushion_recipe_id ? Number(piece.cushion_recipe_id) : null,
          unit_price: Number(piece.unit_price) || 0,
        }))
        payload.build_model = 'frame_line'
        if (productForm.suite_pieces?.length) {
          payload.default_price = suiteTotal(productForm.suite_pieces)
        }
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

  const toggleManualStockLock = async (next) => {
    setLockBusy(true)
    try {
      await configApi.saveInventorySettings({ manual_stock_locked: next })
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setLockBusy(false)
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
    <div className={fromLegacy("page products-page")}>
      <div className={fromLegacy("products-page-header")}>
        <div>
          <h1 className={fromLegacy("page-title")}>محصولات</h1>
          {canLockManualStock && !isFactory && (
            <label className={fromLegacy("checkbox-row")}>
              <input
                type="checkbox"
                checked={manualStockLocked}
                disabled={lockBusy}
                onChange={(e) => toggleManualStockLock(e.target.checked)}
              />
              قفل تغییر دستی موجودی
            </label>
          )}
          {manualStockLocked && (
            <p className={fromLegacy("muted small")}>کسر موجودی با ثبت فاکتور همچنان خودکار است.</p>
          )}
        </div>
        {canManage && (
          <div className={fromLegacy("products-header-actions")}>
            {canManageCategories && (
              <Button type="button" variant="ghost" onClick={openCreateCategory}>+ دسته</Button>
            )}
            <Button type="button" onClick={openCreateProduct}>+ محصول</Button>
            {!manualStockLocked && (
              <Button type="button" variant="ghost" onClick={() => setTransferOpen(true)}>انتقال موجودی</Button>
            )}
          </div>
        )}
      </div>

      {error && <div className={fromLegacy("alert-error")}>{error}</div>}

      {topSelling.length > 0 && (
        <Card title="پرفروش‌ترین کالاها" className={fromLegacy("analytics-card")}>
          <>
            <div className={fromLegacy("table-wrap top-selling-table-desktop")}>
              <table className={fromLegacy("table table-compact")}>
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
            <div className={fromLegacy("top-selling-cards-mobile")}>
              {topSelling.map((item, idx) => (
                <div key={`${item.product_id || item.product_name}-${idx}`} className={fromLegacy("m-card")}>
                  <div className={fromLegacy("m-card-head")}>
                    <strong>{idx + 1}. {item.product_name}</strong>
                    <span>{formatMoney(item.total_revenue)}</span>
                  </div>
                  <div className={fromLegacy("m-card-grid")}>
                    <div><span className={fromLegacy("muted")}>مدل</span>{item.product_model || '—'}</div>
                    <div><span className={fromLegacy("muted")}>پارچه</span>{item.fabric || '—'}</div>
                    <div><span className={fromLegacy("muted")}>تعداد فروش</span><strong>{item.total_quantity}</strong></div>
                    <div><span className={fromLegacy("muted")}>فاکتور</span>{item.sales_count}</div>
                  </div>
                </div>
              ))}
            </div>
          </>
        </Card>
      )}

      <div className={fromLegacy("category-scroll")}>
        <button
          type="button"
          className={fromLegacy(`category-chip${!categoryFilter ? ' active' : ''}`)}
          onClick={() => setCategoryFilter('')}
        >
          همه
        </button>
        {categories.map((c) => (
          <button
            key={c.id}
            type="button"
            className={fromLegacy(`category-chip${categoryFilter === String(c.id) ? ' active' : ''}`)}
            style={{ '--cat-color': c.color }}
            onClick={() => setCategoryFilter(String(c.id))}
          >
            <span>{c.icon}</span> {c.name}
            <span className={fromLegacy("category-count")}>{c.product_count}</span>
          </button>
        ))}
      </div>

      <Card>
        <FilterBar>
          <Field label="جستجو">
            <input
              className={fromLegacy("search-input")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="نام، کد، برند یا رنگ…"
            />
          </Field>
          <Field label="دسته">
            <Select value={categoryFilter} onChange={setCategoryFilter} options={categoryOptions} placeholder="همه" />
          </Field>
          {canManage && (
            <Field label="وضعیت">
              <Select
                value={activeFilter}
                onChange={setActiveFilter}
                options={[
                  { value: '', label: 'همه' },
                  { value: '1', label: 'فعال' },
                  { value: '0', label: 'غیرفعال' },
                ]}
                placeholder="همه"
              />
            </Field>
          )}
        </FilterBar>

        {loading ? (
          <div className={fromLegacy("loading")}>در حال بارگذاری…</div>
        ) : products.length === 0 ? (
          <EmptyState text="محصولی یافت نشد." />
        ) : (
          <>
          <div className={fromLegacy("product-catalog-grid")}>
            {products.map((p) => (
              <article key={p.id} className={fromLegacy(`product-card${p.is_active ? '' : ' inactive'}`)}>
                <div className={fromLegacy("product-card-head")}>
                  <div>
                    {p.category && (
                      <Badge color={p.category.color}>{p.category.icon} {p.category.name}</Badge>
                    )}
                    <h3>{p.name}</h3>
                    {p.product_model && <p className={fromLegacy("muted small")}>مدل: {p.product_model}</p>}
                    {p.fabric && <p className={fromLegacy("muted small")}>پارچه: {p.fabric}</p>}
                    {p.sku && <p className={fromLegacy("muted small ltr")}>SKU: {p.sku}</p>}
                  </div>
                  {!p.is_active && <Badge color="#94a3b8">غیرفعال</Badge>}
                </div>

                {p.variants?.length > 0 && (
                  <div className={fromLegacy("product-color-swatches")}>
                    {p.variants.map((v) => (
                      <span
                        key={v.id}
                        className={fromLegacy("color-swatch")}
                        title={v.color_name}
                        style={{ background: v.color_hex, borderColor: v.color_hex === '#f8fafc' ? '#cbd5e1' : v.color_hex }}
                      />
                    ))}
                  </div>
                )}

                <div className={fromLegacy("product-card-meta")}>
                  {showSalesPrice && p.display_price != null && (
                    <strong>{formatMoney(p.display_price)}</strong>
                  )}
                  {showCosts && p.material_cost_total != null && (
                    <span className={fromLegacy("muted small")}>
                      تمام‌شده: {formatMoney(p.material_cost_total)}
                    </span>
                  )}
                  {isOffice && p.profit_margin != null && (
                    <span className={fromLegacy(`small${p.profit_margin >= 0 ? ' text-success' : ' text-danger'}`)}>
                      سود: {formatMoney(p.profit_margin)}
                    </span>
                  )}
                  {isFactory && p.material_cost_total != null && (
                    <strong>تمام‌شده: {formatMoney(p.material_cost_total)}</strong>
                  )}
                  <span className={fromLegacy("muted")}>{p.variants?.length || 0} رنگ</span>
                  {p.furniture_workset?.name && (
                    <span className={fromLegacy("muted small")}>دست: {p.furniture_workset.name}</span>
                  )}
                  {(p.suite_config || []).length > 0 && (
                    <span className={fromLegacy("muted small")}>
                      {(p.suite_config || []).map((piece) => `${piece.quantity}× ${piece.piece_label}`).join('، ')}
                    </span>
                  )}
                  {p.variants?.some((v) => v.stock_summary) && (
                    <p className={fromLegacy("muted small")}>
                      {p.variants.map((v) => v.stock_summary).filter(Boolean).join(' | ')}
                    </p>
                  )}
                  {showCosts && p.materials?.length > 0 && (
                    <span className={fromLegacy("muted")}>{p.materials.length} متریال</span>
                  )}
                  {(p.suite_config || []).length > 0 ? (
                    <span className={fromLegacy("muted small")}>
                      {(p.suite_config || []).map((piece) => {
                        const fabric = piece.fabric?.name
                        const paint = piece.needs_paint === false ? 'بدون رنگ' : piece.paint?.name
                        return [piece.piece_label, fabric && `پارچه ${fabric}`, paint && (piece.needs_paint === false ? paint : `رنگ ${paint}`)].filter(Boolean).join(' / ')
                      }).join(' • ')}
                    </span>
                  ) : (p.paint_recipe || p.fabric_recipe || p.foam_recipe || p.cushion_recipe || p.webbing_recipe) && (
                    <span className={fromLegacy("muted small")}>
                      {[
                        p.needs_paint === false ? 'بدون رنگ' : (p.paint_recipe?.name && `رنگ ${p.paint_recipe.name}`),
                        p.fabric_recipe?.name && `پارچه ${p.fabric_recipe.name}`,
                        p.foam_recipe?.name && `اسفنج ${p.foam_recipe.name}`,
                        p.webbing_recipe?.name && `تسمه ${p.webbing_recipe.name}`,
                        p.cushion_recipe?.name && `کوسن ${p.cushion_recipe.name}`,
                      ].filter(Boolean).join(' • ')}
                    </span>
                  )}
                </div>

                {showCosts && p.materials?.length > 0 && (
                  <ul className={fromLegacy("product-materials-preview muted small")}>
                    {p.materials.map((pm) => (
                      <li key={pm.id}>
                        {pm.material?.name}
                        {pm.material?.color_name ? ` (${pm.material.color_name})` : ''}
                        {' × '}{pm.quantity}
                      </li>
                    ))}
                  </ul>
                )}

                {p.description && <p className={fromLegacy("product-card-desc muted")}>{p.description}</p>}

                {canManage && (
                  <div className={fromLegacy("product-card-actions")}>
                    <button type="button" className={fromLegacy("link")} onClick={() => openEditProduct(p)}>ویرایش</button>
                    {canDelete && (
                      <button type="button" className={fromLegacy("link danger")} onClick={() => removeProduct(p)}>حذف</button>
                    )}
                  </div>
                )}
              </article>
            ))}
          </div>
          <LoadMoreButton
            hasMore={products.length < total}
            loading={loadingMore}
            onClick={() => load({ append: true, offset: offset + PAGE_SIZE })}
          />
          </>
        )}
      </Card>

      {canManageCategories && categories.length > 0 && (
        <Card title="دسته‌بندی‌ها">
          <div className={fromLegacy("category-manage-list")}>
            {categories.map((c) => (
              <div key={c.id} className={fromLegacy("category-manage-row")}>
                <span className={fromLegacy("category-manage-icon")} style={{ background: c.color }}>{c.icon}</span>
                <div className={fromLegacy("category-manage-info")}>
                  <strong>{c.name}</strong>
                  <span className={fromLegacy("muted")}>{c.product_count} محصول</span>
                </div>
                <div className={fromLegacy("row-actions")}>
                  <button type="button" className={fromLegacy("link")} onClick={() => openEditCategory(c)}>ویرایش</button>
                  <button type="button" className={fromLegacy("link danger")} onClick={() => removeCategory(c)}>حذف</button>
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
        <form onSubmit={saveProduct} className={fromLegacy("form product-form")}>
          <div className={fromLegacy("form-grid-2")}>
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
              <input className={fromLegacy("ltr")} value={productForm.sku} onChange={(e) => setProductForm({ ...productForm, sku: e.target.value })} />
            </Field>
            <Field label="برند">
              <input value={productForm.brand} onChange={(e) => setProductForm({ ...productForm, brand: e.target.value })} />
            </Field>
            <Field label="مدل">
              <input value={productForm.product_model} onChange={(e) => setProductForm({ ...productForm, product_model: e.target.value })} placeholder="مثلاً کلاسیک" />
            </Field>
            <Field label="واحد">
              <input value={productForm.unit} onChange={(e) => setProductForm({ ...productForm, unit: e.target.value })} placeholder="عدد" />
            </Field>
            {canManageSales && !productForm.suite_pieces.length && (
              <>
                <Field label="قیمت فروش (ریال)">
                  <MoneyInput min="0" value={productForm.default_price} onChange={(e) => setProductForm({ ...productForm, default_price: e.target.value })} required />
                </Field>
                <Field label="حاشیه سود هدف (درصد)">
                  <input className={fromLegacy('ltr')} type="number" min="0" max="100" step="0.01" value={productForm.target_margin_percent || ''} onChange={(e) => setProductForm({ ...productForm, target_margin_percent: e.target.value })} placeholder="اختیاری" />
                </Field>
              </>
            )}
          </div>

          <Field label="توضیحات">
            <textarea rows={2} value={productForm.description} onChange={(e) => setProductForm({ ...productForm, description: e.target.value })} />
          </Field>

          {(showCosts || canEditMaterials) && (
            <div className={fromLegacy("product-variants-section")}>
              <div className={fromLegacy("section-head")}>
                <h4>متریال</h4>
                {canEditMaterials && (
                  <Button type="button" variant="ghost" onClick={addProductMaterial}>+ متریال</Button>
                )}
              </div>
              {(productForm.materials || []).length === 0 && !canEditMaterials && (
                <p className={fromLegacy("muted small")}>متریالی تعریف نشده.</p>
              )}
              {(productForm.materials || []).map((m, idx) => (
                <div key={idx} className={fromLegacy("variant-row product-material-row")}>
                  <div className={fromLegacy("form-grid-2 variant-fields")}>
                    <Field label="متریال">
                      {canEditMaterials ? (
                        <Select
                          value={m.material_id}
                          onChange={(v) => updateProductMaterial(idx, 'material_id', v)}
                          options={[{ value: '', label: 'انتخاب…' }, ...materialOptions]}
                          placeholder="انتخاب متریال"
                        />
                      ) : (
                        <input disabled value={materialOptions.find((o) => o.value === m.material_id)?.label || '—'} />
                      )}
                    </Field>
                    <Field label="مقدار مصرف">
                      <input
                        className={fromLegacy("ltr")}
                        type="number"
                        min="0.001"
                        step="0.001"
                        value={m.quantity}
                        onChange={(e) => updateProductMaterial(idx, 'quantity', e.target.value)}
                        disabled={!canEditMaterials}
                      />
                    </Field>
                    <Field label="ضایعات عادی ٪">
                      <input
                        className={fromLegacy("ltr")}
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={m.normal_spoilage_rate ?? 0}
                        onChange={(e) => updateProductMaterial(idx, 'normal_spoilage_rate', e.target.value)}
                        disabled={!canEditMaterials}
                      />
                    </Field>
                  </div>
                  {canEditMaterials && (
                    <button type="button" className={fromLegacy("link danger variant-remove")} onClick={() => removeProductMaterial(idx)}>حذف</button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className={fromLegacy("product-variants-section")}>
            <div className={fromLegacy("section-head")}>
              <h4>دست و رنگ/پارچه قطعات</h4>
              <Button type="button" variant="ghost" onClick={addVariant}>+ رنگ</Button>
            </div>
            {(isFactory || canEditMaterials) && (
              <Field label="دست">
                <Select
                  value={productForm.workset_id}
                  onChange={onWorksetChange}
                  options={worksetOptions}
                  disabled={!canEditMaterials}
                />
              </Field>
            )}
            {productForm.variants.map((v, idx) => (
              <div key={idx} className={fromLegacy("variant-row")}>
                <div className={fromLegacy("variant-color-presets")}>
                  {COLOR_PRESETS.map((preset) => (
                    <button
                      key={preset.hex}
                      type="button"
                      className={fromLegacy("color-preset-btn")}
                      title={preset.name}
                      style={{ background: preset.hex, borderColor: preset.hex === '#f8fafc' ? '#cbd5e1' : preset.hex }}
                      onClick={() => applyColorPreset(idx, preset)}
                    />
                  ))}
                </div>
                <Field label="رنگ">
                  <div className="color-input-one">
                    <input
                      className={fromLegacy("ltr")}
                      type="color"
                      value={v.color_hex}
                      onChange={(e) => updateVariant(idx, 'color_hex', e.target.value)}
                      aria-label="انتخاب رنگ"
                    />
                    <input
                      value={v.color_name}
                      onChange={(e) => updateVariant(idx, 'color_name', e.target.value)}
                      placeholder="مثلاً مشکی"
                    />
                  </div>
                </Field>
                <div className="stock-location-grid">
                  {(v.stock_by_location?.length ? v.stock_by_location : locationStocksFrom(stockLocations)).map((row) => (
                    <Field key={row.key} label={`موجودی ${row.label || row.key}`}>
                      <input
                        className={fromLegacy("ltr")}
                        type="number"
                        min="0"
                        value={row.quantity}
                        onChange={(e) => updateVariantStock(idx, row.key, e.target.value)}
                        placeholder="—"
                        disabled={manualStockLocked}
                      />
                    </Field>
                  ))}
                </div>
                {productForm.variants.length > 1 && (
                  <button type="button" className={fromLegacy("link danger variant-remove")} onClick={() => removeVariant(idx)}>حذف رنگ</button>
                )}
              </div>
            ))}
            {(isFactory || canEditMaterials) && !productForm.workset_id && (
              <p className={fromLegacy('muted small')}>اول دست را از تولید کلاف انتخاب کنید؛ بعد برای هر قطعه رنگ و پارچه بگذارید.</p>
            )}
            {productForm.workset_id && productForm.suite_pieces.length === 0 && (
              <p className={fromLegacy('muted small')}>این دست قطعه‌ای ندارد. اول در تولید کلاف تعداد قطعات را بگذارید.</p>
            )}
            {productForm.suite_pieces.map((piece, idx) => (
              <div key={`${piece.piece_kind}-${piece.arm_style}-${idx}`} className={fromLegacy('frame-model-block')}>
                <div className={fromLegacy('section-head')}>
                  <strong>{piece.piece_label}</strong>
                  <span className={fromLegacy('muted small')}>تعداد از دست: {piece.quantity}</span>
                </div>
                <div className={fromLegacy('form-grid-2')}>
                  <label className={fromLegacy('checkbox-row')}>
                    <input
                      type="checkbox"
                      checked={piece.needs_paint !== false}
                      onChange={(e) => updateSuitePiece(idx, 'needs_paint', e.target.checked)}
                      disabled={!canEditMaterials}
                    />
                    رنگ دارد
                  </label>
                  {piece.needs_paint !== false && (
                    <Field label="رنگ">
                      <Select
                        value={piece.paint_recipe_id}
                        onChange={(v) => updateSuitePiece(idx, 'paint_recipe_id', v)}
                        options={recipeOptions('paint')}
                        disabled={!canEditMaterials}
                      />
                    </Field>
                  )}
                  <Field label="پارچه">
                    <Select
                      value={piece.fabric_recipe_id}
                      onChange={(v) => updateSuitePiece(idx, 'fabric_recipe_id', v)}
                      options={recipeOptions('fabric')}
                      disabled={!canEditMaterials}
                    />
                  </Field>
                  <Field label="اسفنج">
                    <Select
                      value={piece.foam_recipe_id}
                      onChange={(v) => updateSuitePiece(idx, 'foam_recipe_id', v)}
                      options={recipeOptions('foam')}
                      disabled={!canEditMaterials}
                    />
                  </Field>
                  <Field label="تسمه">
                    <Select
                      value={piece.webbing_recipe_id}
                      onChange={(v) => updateSuitePiece(idx, 'webbing_recipe_id', v)}
                      options={recipeOptions('webbing')}
                      disabled={!canEditMaterials}
                    />
                  </Field>
                  <Field label="کوسن">
                    <Select
                      value={piece.cushion_recipe_id}
                      onChange={(v) => updateSuitePiece(idx, 'cushion_recipe_id', v)}
                      options={recipeOptions('cushion')}
                      disabled={!canEditMaterials}
                    />
                  </Field>
                  {(canManageSales || canEditMaterials) && (
                    <Field label="قیمت این قطعه (ریال)">
                      <MoneyInput
                        min="0"
                        value={piece.unit_price}
                        onChange={(e) => updateSuitePiece(idx, 'unit_price', e.target.value)}
                        disabled={!canEditMaterials && !canManageSales}
                      />
                    </Field>
                  )}
                </div>
                {['paint', 'fabric', 'foam', 'webbing', 'cushion'].map((kind) => {
                  const preview = selectedRecipePreview(kind, piece[`${kind}_recipe_id`])
                  const labels = { paint: 'رنگ', fabric: 'پارچه', foam: 'اسفنج', webbing: 'تسمه', cushion: 'کوسن' }
                  return preview ? (
                    <p key={kind} className={fromLegacy('muted small')}>مصرف {labels[kind]}: {preview}</p>
                  ) : null
                })}
              </div>
            ))}
            {productForm.suite_pieces.length > 0 && (canManageSales || canEditMaterials) && (
              <p className={fromLegacy('muted')}>جمع قیمت دست: {formatMoney(suiteTotal(productForm.suite_pieces))}</p>
            )}
          </div>

          <label className={fromLegacy("checkbox-row")}>
            <input type="checkbox" checked={productForm.is_active} onChange={(e) => setProductForm({ ...productForm, is_active: e.target.checked })} />
            فعال
          </label>

          <div className={fromLegacy("form-actions")}>
            <Button type="button" variant="ghost" onClick={() => setProductModal(false)} disabled={saving}>انصراف</Button>
            <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره محصول'}</Button>
          </div>
        </form>
      </Modal>

      <Modal title={editingCategory ? 'ویرایش دسته' : 'دسته جدید'} open={categoryModal} onClose={() => !saving && setCategoryModal(false)}>
        <form onSubmit={saveCategory} className={fromLegacy("form")}>
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
            <input className={fromLegacy("ltr")} type="number" min="0" value={categoryForm.sort_order} onChange={(e) => setCategoryForm({ ...categoryForm, sort_order: e.target.value })} />
          </Field>
          <Field label="توضیحات">
            <textarea rows={2} value={categoryForm.description} onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })} />
          </Field>
          <label className={fromLegacy("checkbox-row")}>
            <input type="checkbox" checked={categoryForm.is_active} onChange={(e) => setCategoryForm({ ...categoryForm, is_active: e.target.checked })} />
            فعال
          </label>
          <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره دسته'}</Button>
        </form>
      </Modal>

      <Modal title="انتقال موجودی بین انبار و شعبه" open={transferOpen} onClose={() => !transferBusy && setTransferOpen(false)}>
        <form
          className={fromLegacy("form")}
          onSubmit={async (e) => {
            e.preventDefault()
            const source = stockLocations.find((l) => l.key === transferForm.source)
            const destination = stockLocations.find((l) => l.key === transferForm.destination)
            if (!source || !destination) {
              setError('مبدأ و مقصد را انتخاب کنید.')
              return
            }
            setTransferBusy(true)
            try {
              await productsApi.transferStock({
                variant_id: Number(transferForm.variant_id),
                source,
                destination,
                quantity: Number(transferForm.quantity),
              })
              setTransferOpen(false)
              setTransferForm({ variant_id: '', source: '', destination: '', quantity: '' })
              load()
            } catch (err) {
              setError(err.message)
            } finally {
              setTransferBusy(false)
            }
          }}
        >
          <Field label="رنگ محصول">
            <Select
              value={transferForm.variant_id}
              onChange={(v) => setTransferForm({ ...transferForm, variant_id: v })}
              options={[
                { value: '', label: 'انتخاب…' },
                ...products.flatMap((p) => (p.variants || []).map((v) => ({
                  value: String(v.id),
                  label: `${p.name} — ${v.color_name}${v.stock_summary ? ` (${v.stock_summary})` : ''}`,
                }))),
              ]}
              required
            />
          </Field>
          <Field label="از">
            <Select
              value={transferForm.source}
              onChange={(v) => setTransferForm({ ...transferForm, source: v })}
              options={[{ value: '', label: 'انتخاب مبدأ…' }, ...stockLocations.map((l) => ({ value: l.key, label: l.label }))]}
              required
            />
          </Field>
          <Field label="به">
            <Select
              value={transferForm.destination}
              onChange={(v) => setTransferForm({ ...transferForm, destination: v })}
              options={[{ value: '', label: 'انتخاب مقصد…' }, ...stockLocations.map((l) => ({ value: l.key, label: l.label }))]}
              required
            />
          </Field>
          <Field label="تعداد">
            <input className={fromLegacy("ltr")} type="number" min="1" value={transferForm.quantity} onChange={(e) => setTransferForm({ ...transferForm, quantity: e.target.value })} required />
          </Field>
          <Button type="submit" disabled={transferBusy}>{transferBusy ? 'در حال انتقال…' : 'انتقال'}</Button>
        </form>
      </Modal>
    </div>
  )
}
