import { useEffect, useMemo, useState } from 'react'
import { productsApi } from '../api/client'
import { Button, Field, Modal } from './ui'
import { formatMoney } from '../utils/format'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_LINE = {
  product_id: '',
  variant_id: '',
  product_name: '',
  product_model: '',
  fabric: '',
  color_name: '',
  color_hex: '',
  quantity: 1,
  unit_price: '',
}

function catalogPrice(product) {
  return Number(product?.default_price || product?.display_price || 0)
}

export default function ProductLines({ lines, onChange }) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [activeLineIdx, setActiveLineIdx] = useState(0)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [selectedVariant, setSelectedVariant] = useState(null)

  useEffect(() => {
    if (!pickerOpen) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const [prods, cats] = await Promise.all([
          productsApi.list({
            search: search.trim(),
            category_id: categoryFilter || undefined,
            limit: 50,
          }),
          productsApi.categories({ active: true }),
        ])
        if (!cancelled) {
          setProducts(prods.results || [])
          setCategories(cats.results || [])
        }
      } catch {
        if (!cancelled) setProducts([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    const t = setTimeout(load, 250)
    return () => { cancelled = true; clearTimeout(t) }
  }, [pickerOpen, search, categoryFilter])

  const updateLine = (idx, patch) => {
    onChange(lines.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }

  const addLine = () => onChange([...lines, { ...EMPTY_LINE }])

  const openPicker = (idx) => {
    setActiveLineIdx(idx)
    setSelectedProduct(null)
    setSelectedVariant(null)
    setSearch('')
    setCategoryFilter('')
    setPickerOpen(true)
  }

  const confirmPick = () => {
    if (!selectedProduct) return
    const variant = selectedVariant || selectedProduct.variants?.[0]
    const price = catalogPrice(selectedProduct)
    if (price <= 0) return

    const nextLines = [...lines]
    if (nextLines.length <= activeLineIdx) {
      nextLines.push({ ...EMPTY_LINE })
    }
    nextLines[activeLineIdx] = {
      ...nextLines[activeLineIdx],
      product_id: selectedProduct.id,
      variant_id: variant?.id || '',
      product_name: selectedProduct.name,
      product_model: selectedProduct.product_model || '',
      fabric: selectedProduct.fabric || '',
      color_name: variant?.color_name || '',
      color_hex: variant?.color_hex || '',
      unit_price: String(price),
      quantity: nextLines[activeLineIdx]?.quantity || 1,
    }
    onChange(nextLines)
    setPickerOpen(false)
  }

  const pickerPrice = selectedProduct ? catalogPrice(selectedProduct) : 0

  const total = lines.reduce((s, l) => s + Number(l.unit_price || 0) * Number(l.quantity || 1), 0)

  const filteredCategories = useMemo(
    () => [{ id: '', name: 'همه' }, ...categories],
    [categories],
  )

  return (
    <div className={fromLegacy("product-lines")}>
      {lines.map((line, idx) => (
        <div key={idx} className={fromLegacy("sale-line-card")}>
          <div className={fromLegacy("sale-line-head")}>
            <strong>ردیف {idx + 1}</strong>
            {line.color_hex && (
              <span className={fromLegacy("line-color-badge")} style={{ background: line.color_hex }} title={line.color_name} />
            )}
          </div>
          <div className={fromLegacy("sale-line-body")}>
            {line.product_id ? (
              <div className={fromLegacy("sale-line-product-readonly")}>
                <div className={fromLegacy("sale-line-product-name")}>
                  <strong>{line.product_name}</strong>
                  {line.color_name && <span className={fromLegacy("muted")}> — {line.color_name}</span>}
                </div>
                <div className={fromLegacy("sale-line-meta-grid")}>
                  {line.product_model && <span><em className={fromLegacy("muted")}>مدل:</em> {line.product_model}</span>}
                  {line.fabric && <span><em className={fromLegacy("muted")}>پارچه:</em> {line.fabric}</span>}
                  {line.unit_price && (
                    <span><em className={fromLegacy("muted")}>قیمت واحد:</em> {formatMoney(line.unit_price)}</span>
                  )}
                </div>
                <Button type="button" variant="ghost" onClick={() => openPicker(idx)}>تغییر محصول</Button>
              </div>
            ) : (
              <Field label="محصول">
                <Button type="button" onClick={() => openPicker(idx)}>انتخاب از کاتالوگ</Button>
              </Field>
            )}
            <Field label="تعداد">
              <input className={fromLegacy("ltr")} type="number" min="1" value={line.quantity} onChange={(e) => updateLine(idx, { quantity: e.target.value })} />
            </Field>
            {line.product_id && line.unit_price && (
              <p className={fromLegacy("muted small")}>جمع ردیف: {formatMoney(Number(line.unit_price) * Number(line.quantity || 1))}</p>
            )}
          </div>
        </div>
      ))}

      <Button type="button" variant="ghost" onClick={addLine}>+ ردیف محصول</Button>
      {lines.length > 0 && <p className={fromLegacy("muted")}>جمع محصولات: {formatMoney(total)}</p>}

      <Modal title="انتخاب محصول" open={pickerOpen} onClose={() => setPickerOpen(false)} wide>
        <div className={fromLegacy("product-picker")}>
          <div className={fromLegacy("product-picker-filters")}>
            <input
              className={fromLegacy("search-input")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجوی محصول…"
            />
            <div className={fromLegacy("category-scroll compact")}>
              {filteredCategories.map((c) => (
                <button
                  key={c.id || 'all'}
                  type="button"
                  className={fromLegacy(`category-chip${String(categoryFilter) === String(c.id || '') ? ' active' : ''}`)}
                  onClick={() => setCategoryFilter(c.id ? String(c.id) : '')}
                >
                  {c.icon ? `${c.icon} ` : ''}{c.name}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <p className={fromLegacy("muted")}>در حال جستجو…</p>
          ) : products.length === 0 ? (
            <p className={fromLegacy("muted")}>محصولی یافت نشد.</p>
          ) : (
            <div className={fromLegacy("product-picker-grid")}>
              {products.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={fromLegacy(`product-picker-item${selectedProduct?.id === p.id ? ' selected' : ''}`)}
                  onClick={() => {
                    setSelectedProduct(p)
                    setSelectedVariant(p.variants?.[0] || null)
                  }}
                >
                  <strong>{p.name}</strong>
                  <span className={fromLegacy("muted")}>{formatMoney(catalogPrice(p))}</span>
                  {p.product_model && <span className={fromLegacy("muted small")}>مدل: {p.product_model}</span>}
                  {p.fabric && <span className={fromLegacy("muted small")}>پارچه: {p.fabric}</span>}
                  {p.variants?.length > 0 && (
                    <div className={fromLegacy("product-color-swatches small")}>
                      {p.variants.map((v) => (
                        <span key={v.id} className={fromLegacy("color-swatch")} style={{ background: v.color_hex }} title={v.color_name} />
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}

          {selectedProduct && (
            <div className={fromLegacy("variant-picker-panel")}>
              <h4>{selectedProduct.name}</h4>
              <div className={fromLegacy("sale-line-meta-grid")}>
                {selectedProduct.product_model && <span><em className={fromLegacy("muted")}>مدل:</em> {selectedProduct.product_model}</span>}
                {selectedProduct.fabric && <span><em className={fromLegacy("muted")}>پارچه:</em> {selectedProduct.fabric}</span>}
              </div>
              {selectedProduct.variants?.length ? (
                <div className={fromLegacy("variant-picker-options")}>
                  {selectedProduct.variants.map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      className={fromLegacy(`variant-option${selectedVariant?.id === v.id ? ' active' : ''}`)}
                      onClick={() => setSelectedVariant(v)}
                    >
                      <span className={fromLegacy("color-swatch")} style={{ background: v.color_hex }} />
                      <span>{v.color_name}</span>
                    </button>
                  ))}
                </div>
              ) : null}
              {pickerPrice > 0 ? (
                <p className={fromLegacy("muted")}>قیمت: <strong>{formatMoney(pickerPrice)}</strong></p>
              ) : (
                <p className={fromLegacy("alert-error")} style={{ marginTop: 8 }}>این محصول قیمت ندارد — ابتدا در بخش محصولات قیمت را تنظیم کنید.</p>
              )}
            </div>
          )}

          <div className={fromLegacy("form-actions")}>
            <Button type="button" variant="ghost" onClick={() => setPickerOpen(false)}>انصراف</Button>
            <Button
              type="button"
              onClick={confirmPick}
              disabled={!selectedProduct || pickerPrice <= 0}
            >
              افزودن به فاکتور
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export { EMPTY_LINE as EMPTY_PRODUCT_LINE }
