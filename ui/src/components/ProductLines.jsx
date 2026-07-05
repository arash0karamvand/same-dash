import { useEffect, useMemo, useState } from 'react'
import { productsApi } from '../api/client'
import MoneyInput from './MoneyInput'
import { Button, Field, Modal } from './ui'
import { formatMoney } from '../utils/format'

const EMPTY_LINE = {
  product_id: '',
  variant_id: '',
  product_name: '',
  color_name: '',
  color_hex: '',
  quantity: 1,
  unit_price: '',
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
    const displayName = variant
      ? `${selectedProduct.name} — ${variant.color_name}`
      : selectedProduct.name
    const price = variant ? variant.price : selectedProduct.display_price

    const nextLines = [...lines]
    if (nextLines.length <= activeLineIdx) {
      nextLines.push({ ...EMPTY_LINE })
    }
    nextLines[activeLineIdx] = {
      ...nextLines[activeLineIdx],
      product_id: selectedProduct.id,
      variant_id: variant?.id || '',
      product_name: displayName,
      color_name: variant?.color_name || '',
      color_hex: variant?.color_hex || '',
      unit_price: String(price ?? ''),
      quantity: nextLines[activeLineIdx]?.quantity || 1,
    }
    onChange(nextLines)
    setPickerOpen(false)
  }

  const total = lines.reduce((s, l) => s + Number(l.unit_price || 0) * Number(l.quantity || 1), 0)

  const filteredCategories = useMemo(
    () => [{ id: '', name: 'همه' }, ...categories],
    [categories],
  )

  return (
    <div className="product-lines">
      {lines.map((line, idx) => (
        <div key={idx} className="sale-line-card">
          <div className="sale-line-head">
            <strong>ردیف {idx + 1}</strong>
            {line.color_hex && (
              <span className="line-color-badge" style={{ background: line.color_hex }} title={line.color_name} />
            )}
          </div>
          <div className="sale-line-body">
            <Field label="محصول">
              <div className="product-pick-row">
                <input
                  value={line.product_name}
                  onChange={(e) => updateLine(idx, { product_name: e.target.value, product_id: '', variant_id: '' })}
                  placeholder="انتخاب یا تایپ دستی…"
                  required
                />
                <Button type="button" variant="ghost" onClick={() => openPicker(idx)}>انتخاب</Button>
              </div>
            </Field>
            <div className="form-grid-2">
              <Field label="تعداد">
                <input className="ltr" type="number" min="1" value={line.quantity} onChange={(e) => updateLine(idx, { quantity: e.target.value })} />
              </Field>
              <Field label="قیمت واحد">
                <MoneyInput min="0" value={line.unit_price} onChange={(e) => updateLine(idx, { unit_price: e.target.value })} required />
              </Field>
            </div>
          </div>
        </div>
      ))}

      <Button type="button" variant="ghost" onClick={addLine}>+ ردیف محصول</Button>
      {lines.length > 0 && <p className="muted">جمع محصولات: {formatMoney(total)}</p>}

      <Modal title="انتخاب محصول" open={pickerOpen} onClose={() => setPickerOpen(false)} wide>
        <div className="product-picker">
          <div className="product-picker-filters">
            <input
              className="search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجوی محصول…"
            />
            <div className="category-scroll compact">
              {filteredCategories.map((c) => (
                <button
                  key={c.id || 'all'}
                  type="button"
                  className={`category-chip${String(categoryFilter) === String(c.id || '') ? ' active' : ''}`}
                  onClick={() => setCategoryFilter(c.id ? String(c.id) : '')}
                >
                  {c.icon ? `${c.icon} ` : ''}{c.name}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <p className="muted">در حال جستجو…</p>
          ) : products.length === 0 ? (
            <p className="muted">محصولی یافت نشد.</p>
          ) : (
            <div className="product-picker-grid">
              {products.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`product-picker-item${selectedProduct?.id === p.id ? ' selected' : ''}`}
                  onClick={() => {
                    setSelectedProduct(p)
                    setSelectedVariant(p.variants?.[0] || null)
                  }}
                >
                  <strong>{p.name}</strong>
                  <span className="muted">{formatMoney(p.display_price)}</span>
                  {p.variants?.length > 0 && (
                    <div className="product-color-swatches small">
                      {p.variants.map((v) => (
                        <span key={v.id} className="color-swatch" style={{ background: v.color_hex }} />
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}

          {selectedProduct && (
            <div className="variant-picker-panel">
              <h4>{selectedProduct.name} — انتخاب رنگ</h4>
              {selectedProduct.variants?.length ? (
                <div className="variant-picker-options">
                  {selectedProduct.variants.map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      className={`variant-option${selectedVariant?.id === v.id ? ' active' : ''}`}
                      onClick={() => setSelectedVariant(v)}
                    >
                      <span className="color-swatch" style={{ background: v.color_hex }} />
                      <span>{v.color_name}</span>
                      <strong>{formatMoney(v.price)}</strong>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="muted">این محصول رنگ‌بندی ندارد — قیمت: {formatMoney(selectedProduct.display_price)}</p>
              )}
            </div>
          )}

          <div className="form-actions">
            <Button type="button" variant="ghost" onClick={() => setPickerOpen(false)}>انصراف</Button>
            <Button type="button" onClick={confirmPick} disabled={!selectedProduct}>افزودن به فاکتور</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export { EMPTY_LINE as EMPTY_PRODUCT_LINE }
