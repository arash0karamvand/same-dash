import { useEffect, useMemo, useState } from 'react'
import { productsApi } from '../api/client'
import Icon from './icons/Icon'
import { Button, Field, Modal } from './ui'
import { formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'
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

function lineFromPick(pick, quantity = 1) {
  const variant = pick.variant || pick.product.variants?.[0]
  return {
    ...EMPTY_LINE,
    product_id: pick.product.id,
    variant_id: variant?.id || '',
    product_name: pick.product.name,
    product_model: pick.product.product_model || '',
    fabric: pick.product.fabric || '',
    color_name: variant?.color_name || '',
    color_hex: variant?.color_hex || '',
    unit_price: String(catalogPrice(pick.product)),
    quantity,
  }
}

function locationQty(variant, stockSourceKey) {
  if (!variant) return null
  if (stockSourceKey && variant.stock_by_location?.length) {
    const row = variant.stock_by_location.find((item) => item.key === stockSourceKey)
    if (row) return row.quantity
  }
  if (variant.stock_summary) return variant.stock_summary
  if (variant.stock != null && variant.stock !== '') return variant.stock
  return null
}

export default function ProductLines({ lines, onChange, stockSourceKey = '' }) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [activeLineIdx, setActiveLineIdx] = useState(null)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedPicks, setSelectedPicks] = useState([])
  const [focusedProductId, setFocusedProductId] = useState(null)

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

  const removeLine = (idx) => onChange(lines.filter((_, i) => i !== idx))

  const resetPicker = () => {
    setSelectedPicks([])
    setFocusedProductId(null)
    setSearch('')
    setCategoryFilter('')
  }

  const openPicker = (idx = null) => {
    setActiveLineIdx(idx)
    resetPicker()
    setPickerOpen(true)
  }

  const isPicked = (id) => selectedPicks.some((x) => x.product.id === id)

  const selectProduct = (p) => {
    if (!isPicked(p.id)) {
      setSelectedPicks((prev) => [...prev, { product: p, variant: p.variants?.[0] || null }])
    }
    setFocusedProductId(p.id)
  }

  const toggleProduct = (p) => {
    if (isPicked(p.id)) {
      const next = selectedPicks.filter((x) => x.product.id !== p.id)
      setSelectedPicks(next)
      setFocusedProductId((id) => (id === p.id ? (next[next.length - 1]?.product.id || null) : id))
      return
    }
    setSelectedPicks((prev) => [...prev, { product: p, variant: p.variants?.[0] || null }])
    setFocusedProductId(p.id)
  }

  const setPickVariant = (productId, variant) => {
    setSelectedPicks((prev) =>
      prev.map((x) => (x.product.id === productId ? { ...x, variant } : x)),
    )
    setFocusedProductId(productId)
  }

  const pickWithVariant = (p, variant) => {
    setSelectedPicks((prev) => {
      const exists = prev.some((x) => x.product.id === p.id)
      if (exists) return prev.map((x) => (x.product.id === p.id ? { ...x, variant } : x))
      return [...prev, { product: p, variant }]
    })
    setFocusedProductId(p.id)
  }

  const pricedPicks = selectedPicks.filter((x) => catalogPrice(x.product) > 0)

  const confirmPick = () => {
    if (!pricedPicks.length) return

    const newLines = pricedPicks.map((pick, i) => {
      const qty = (activeLineIdx != null && i === 0 && lines[activeLineIdx]?.quantity)
        ? lines[activeLineIdx].quantity
        : 1
      return lineFromPick(pick, qty)
    })

    let nextLines
    if (activeLineIdx != null && activeLineIdx < lines.length) {
      nextLines = [
        ...lines.slice(0, activeLineIdx),
        ...newLines,
        ...lines.slice(activeLineIdx + 1),
      ]
    } else {
      nextLines = [...lines.filter((l) => l.product_id), ...newLines]
    }

    onChange(nextLines)
    setPickerOpen(false)
  }

  const focusedPick =
    selectedPicks.find((x) => x.product.id === focusedProductId) ||
    selectedPicks[selectedPicks.length - 1] ||
    null
  const focusedProduct = focusedPick?.product || null
  const focusedVariant = focusedPick?.variant || null
  const pickerPrice = focusedProduct ? catalogPrice(focusedProduct) : 0

  const total = lines.reduce((s, l) => s + Number(l.unit_price || 0) * Number(l.quantity || 1), 0)

  const filteredCategories = useMemo(
    () => [{ id: '', name: 'همه' }, ...categories],
    [categories],
  )

  const confirmLabel = pricedPicks.length > 1
    ? `افزودن ${toPersianDigits(pricedPicks.length)} محصول به فاکتور`
    : 'افزودن به فاکتور'

  return (
    <div className={fromLegacy("product-lines")}>
      {lines.map((line, idx) => (
        <div key={idx} className={fromLegacy("sale-line-card")}>
          <div className={fromLegacy("sale-line-head")}>
            <strong>ردیف {toPersianDigits(idx + 1)}</strong>
            {line.color_hex && (
              <span className={fromLegacy("line-color-badge")} style={{ background: line.color_hex }} title={line.color_name} />
            )}
            <Button type="button" variant="ghost" size="sm" className={fromLegacy("sale-line-remove")} onClick={() => removeLine(idx)}>
              حذف
            </Button>
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

      <div className={fromLegacy("product-lines-toolbar")}>
        <Button type="button" onClick={() => openPicker()}>انتخاب از کاتالوگ</Button>
      </div>
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
            <p className={fromLegacy("muted small product-picker-hint")}>چند محصول را با هم انتخاب کنید، سپس به فاکتور اضافه کنید.</p>
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
              {products.map((p) => {
                const picked = isPicked(p.id)
                const pick = selectedPicks.find((x) => x.product.id === p.id)
                return (
                  <div
                    key={p.id}
                    role="button"
                    tabIndex={0}
                    className={fromLegacy(`product-picker-item${picked ? ' selected' : ''}${focusedProductId === p.id ? ' focused' : ''}`)}
                    onClick={() => selectProduct(p)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        selectProduct(p)
                      }
                    }}
                  >
                    <button
                      type="button"
                      className={fromLegacy(`product-picker-check${picked ? ' on' : ''}`)}
                      aria-label={picked ? 'حذف از انتخاب' : 'انتخاب'}
                      aria-pressed={picked}
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleProduct(p)
                      }}
                    >
                      {picked ? <Icon name="check" size={12} /> : null}
                    </button>
                    <strong>{p.name}</strong>
                    <span className={fromLegacy("muted")}>{formatMoney(catalogPrice(p))}</span>
                    {p.product_model && <span className={fromLegacy("muted small")}>مدل: {p.product_model}</span>}
                    {p.fabric && <span className={fromLegacy("muted small")}>پارچه: {p.fabric}</span>}
                    {p.variants?.length > 0 && (
                      <div className={fromLegacy("product-color-swatches small")}>
                        {p.variants.map((v) => (
                          <span
                            key={v.id}
                            role="button"
                            tabIndex={0}
                            className={fromLegacy(`color-swatch${pick?.variant?.id === v.id ? ' active' : ''}`)}
                            style={{ background: v.color_hex }}
                            title={`${v.color_name}${locationQty(v, stockSourceKey) != null ? ` — موجودی ${toPersianDigits(locationQty(v, stockSourceKey))}` : ''}`}
                            onClick={(e) => {
                              e.stopPropagation()
                              pickWithVariant(p, v)
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                e.stopPropagation()
                                pickWithVariant(p, v)
                              }
                            }}
                          />
                        ))}
                      </div>
                    )}
                    {pick?.variant && locationQty(pick.variant, stockSourceKey) != null && (
                      <span className={fromLegacy("muted small")}>
                        موجودی: {toPersianDigits(locationQty(pick.variant, stockSourceKey))}
                        {pick.variant.stock_summary && !stockSourceKey ? ` (${pick.variant.stock_summary})` : ''}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {selectedPicks.length > 0 && (
            <div className={fromLegacy("product-picker-selected")}>
              {selectedPicks.map((pick) => (
                <button
                  key={pick.product.id}
                  type="button"
                  className={fromLegacy("product-picker-chip")}
                  onClick={() => toggleProduct(pick.product)}
                >
                  <span>
                    {pick.product.name}
                    {pick.variant?.color_name ? ` — ${pick.variant.color_name}` : ''}
                  </span>
                  <Icon name="x" size={12} />
                </button>
              ))}
            </div>
          )}

          {focusedProduct && (
            <div className={fromLegacy("variant-picker-panel")}>
              <h4>{focusedProduct.name}</h4>
              <div className={fromLegacy("sale-line-meta-grid")}>
                {focusedProduct.product_model && <span><em className={fromLegacy("muted")}>مدل:</em> {focusedProduct.product_model}</span>}
                {focusedProduct.fabric && <span><em className={fromLegacy("muted")}>پارچه:</em> {focusedProduct.fabric}</span>}
              </div>
              {focusedProduct.variants?.length ? (
                <div className={fromLegacy("variant-picker-options")}>
                  {focusedProduct.variants.map((v) => (
                    <button
                      key={v.id}
                      type="button"
                      className={fromLegacy(`variant-option${focusedVariant?.id === v.id ? ' active' : ''}`)}
                      onClick={() => setPickVariant(focusedProduct.id, v)}
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
            {selectedPicks.length > 0 && (
              <p className={fromLegacy("muted small product-picker-count")}>
                {toPersianDigits(selectedPicks.length)} محصول انتخاب شده
              </p>
            )}
            <Button type="button" variant="ghost" onClick={() => setPickerOpen(false)}>انصراف</Button>
            <Button
              type="button"
              onClick={confirmPick}
              disabled={!pricedPicks.length}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export { EMPTY_LINE as EMPTY_PRODUCT_LINE }
