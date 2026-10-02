import { useEffect, useMemo, useRef, useState } from 'react'
import { furnitureWorksetsApi, salesApi } from '../api/client'
import Select from './Select'
import { Button, Field, Modal } from './ui'
import { formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'
import { fromLegacy } from '../styles/tw.js'

const EMPTY_LINE = {
  product_id: '',
  variant_id: '',
  frame_id: '',
  frame_model_id: '',
  frame_config: {},
  workset_config: {},
  furniture_workset_id: '',
  furniture_workset_name: '',
  product_name: '',
  product_model: '',
  fabric: '',
  color_name: '',
  color_hex: '',
  quantity: 1,
  unit_price: '',
  fabric_recipe_id: '',
  paint_recipe_id: '',
  sale_mode: '',
  configuration_mode: 'full',
  catalog_pieces: [],
  quote_status: 'idle',
  price_note: '',
}

const ORDER_MODES = [
  {
    value: 'full',
    title: 'دست کامل',
    description: 'ترکیب کارخانه و قیمت مصوب اداری، بدون تغییر قطعات',
  },
  {
    value: 'custom',
    title: 'کاستوم',
    description: 'ترکیب ثابت؛ رنگ و پارچه را برای کل دست یا هر قطعه تغییر دهید',
  },
  {
    value: 'modular',
    title: 'ماژولار',
    description: 'تعداد قطعات را کم‌وزیاد کنید و مشخصات هر قطعه را جدا بسازید',
  },
]

function uiMode(line) {
  if (line?.sale_mode !== 'custom_set') return 'full'
  return line.configuration_mode
    || line.workset_config?.configuration_mode
    || line.workset_config?.sale_choices?.configuration_mode
    || 'custom'
}

function catalogPrice(product) {
  return Number(product?.default_price || product?.display_price || 0)
}

function jobPieces(product) {
  return product?.workset?.pieces || product?.suite_config || []
}

function pieceSummary(product) {
  const pieces = jobPieces(product)
  if (!pieces.length) return product?.product_model || ''
  return pieces.map((piece) => `${piece.quantity}× ${piece.piece_label}`).join('، ')
}

function fabricSummary(product) {
  const pieces = jobPieces(product)
  const names = [...new Set(pieces.map((piece) => piece.fabric?.name).filter(Boolean))]
  if (names.length) return names.join('، ')
  return product?.fabric || product?.fabric_recipe?.name || ''
}

function consumptionMeters(block) {
  return (block?.materials || []).reduce((sum, row) => sum + Number(row.quantity || 0), 0)
}

function serviceMeters(pieces) {
  return (pieces || []).reduce(
    (sum, piece) => sum + consumptionMeters(piece.fabric) * Number(piece.quantity || 1),
    0,
  )
}

function missingMeterPieces(pieces) {
  return (pieces || [])
    .filter((piece) => consumptionMeters(piece.fabric) <= 0)
    .map((piece) => piece.piece_label || 'قطعه')
}

function recipeLabel(recipe, withRate = false) {
  if (!recipe) return ''
  const color = recipe.color_name && recipe.color_name !== recipe.name ? ` (${recipe.color_name})` : ''
  const rate = withRate && Number(recipe.unit_cost) > 0 ? ` — ${formatMoney(recipe.unit_cost)} هر متر` : ''
  return `${recipe.name}${color}${rate}`
}

function lockedSpecs(pieces) {
  return (pieces || []).map((piece) => {
    const meters = consumptionMeters(piece.fabric)
    const bits = [
      `${toPersianDigits(piece.quantity || 1)}× ${piece.piece_label || 'قطعه'}`,
      meters > 0 ? `${toPersianDigits(meters)} متر` : 'بدون متراژ',
    ]
    if (piece.foam?.name) bits.push(`اسفنج ${piece.foam.name}`)
    if (piece.webbing?.name) bits.push(`تسمه ${piece.webbing.name}`)
    if (piece.cushion?.name) bits.push(`کوسن ${piece.cushion.name}`)
    return bits.join(' · ')
  })
}

function lineFromProduct(product, quantity = 1, saleMode = 'full_set') {
  const variant = product.variants?.[0]
  const pieces = jobPieces(product)
  const configurationMode = saleMode === 'full_set' || saleMode === 'full'
    ? 'full'
    : saleMode === 'custom_set'
      ? 'custom'
      : saleMode
  const apiSaleMode = configurationMode === 'full' ? 'full_set' : 'custom_set'
  const base = {
    ...EMPTY_LINE,
    product_id: product.id,
    variant_id: variant?.id || '',
    frame_id: product.frame_id || '',
    furniture_workset_id: product.furniture_workset_id || '',
    furniture_workset_name: product.furniture_workset?.name || '',
    workset_config: {
      ...(product.workset || {}),
      pieces,
      sale_mode: apiSaleMode,
      configuration_mode: configurationMode,
    },
    catalog_pieces: pieces.map((piece) => ({ ...piece })),
    product_name: product.name,
    product_model: product.furniture_workset?.name || product.product_model || '',
    fabric: fabricSummary(product),
    color_name: variant?.color_name || '',
    color_hex: variant?.color_hex || '',
    unit_price: pieces.length ? '' : String(catalogPrice(product)),
    target_min_price: product.target_min_price || '',
    quantity,
    sale_mode: pieces.length ? apiSaleMode : '',
    configuration_mode: configurationMode,
    quote_status: pieces.length ? 'loading' : 'ready',
    price_note: pieces.length ? 'در حال محاسبه قیمت…' : '',
  }
  return pieces.length ? base : base
}

export default function ProductLines({
  lines,
  onChange,
  seatCount = '',
  onSeatCountChange,
  stockSourceLabel = '',
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [worksets, setWorksets] = useState([])
  const [selectedWorkset, setSelectedWorkset] = useState(null)
  const [worksetProducts, setWorksetProducts] = useState([])
  const [qtys, setQtys] = useState({})
  const [pickModes, setPickModes] = useState({})
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [productSearch, setProductSearch] = useState('')
  const [productLimit, setProductLimit] = useState(24)
  const [paints, setPaints] = useState([])
  const [fabrics, setFabrics] = useState([])
  const linesRef = useRef(lines)
  const quoteTokens = useRef({})
  const quoteTimers = useRef({})

  useEffect(() => {
    linesRef.current = lines
  }, [lines])

  useEffect(() => () => {
    Object.values(quoteTimers.current).forEach(clearTimeout)
  }, [])

  useEffect(() => {
    let cancelled = false
    salesApi.finishOptions()
      .then((data) => {
        if (cancelled) return
        setPaints(data?.paints || [])
        setFabrics(data?.fabrics || [])
      })
      .catch(() => {
        if (!cancelled) {
          setPaints([])
          setFabrics([])
        }
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!pickerOpen) return
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const data = await furnitureWorksetsApi.list({ search: search.trim(), limit: 80 })
        if (!cancelled) setWorksets(data.results || [])
      } catch {
        if (!cancelled) setWorksets([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    const t = setTimeout(load, 200)
    return () => { cancelled = true; clearTimeout(t) }
  }, [pickerOpen, search])

  const openWorkset = async (workset) => {
    setSelectedWorkset(workset)
    setProductSearch('')
    setProductLimit(24)
    setLoading(true)
    try {
      const data = await furnitureWorksetsApi.products(workset.id)
      const results = data.results || []
      setWorksetProducts(results)
      const next = {}
      results.forEach((p) => { next[p.id] = 0 })
      setQtys(next)
      setPickModes(Object.fromEntries(results.map((p) => [p.id, 'full'])))
      if (onSeatCountChange && !seatCount && workset.seat_count) {
        onSeatCountChange(String(workset.seat_count))
      }
    } catch {
      setWorksetProducts([])
    } finally {
      setLoading(false)
    }
  }

  const canAdd = (product) => jobPieces(product).length > 0 || catalogPrice(product) > 0
  const picked = useMemo(
    () => worksetProducts.filter((p) => Number(qtys[p.id] || 0) > 0 && canAdd(p)),
    [worksetProducts, qtys],
  )
  const filteredProducts = useMemo(() => {
    const needle = productSearch.trim().toLocaleLowerCase('fa')
    if (!needle) return worksetProducts
    return worksetProducts.filter((product) => (
      [product.name, product.sku, product.product_model]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase('fa').includes(needle))
    ))
  }, [productSearch, worksetProducts])
  const visibleProducts = filteredProducts.slice(0, productLimit)
  const pickTotal = picked.reduce((sum, product) => {
    if (jobPieces(product).length) return sum
    return sum + catalogPrice(product) * Number(qtys[product.id] || 0)
  }, 0)

  const quoteLine = async (line) => {
    if (!(line.workset_config?.pieces || []).length) return line
    try {
      const quote = await salesApi.bundleQuote({
        product_id: line.product_id,
        sale_mode: line.sale_mode || 'full_set',
        workset_config: {
          ...(line.workset_config || {}),
          sale_mode: line.sale_mode || 'full_set',
        },
      })
      const quotedConfig = quote.workset_config || line.workset_config
      const worksetConfig = uiMode(line) === 'modular'
        ? {
            ...quotedConfig,
            pieces: (line.workset_config?.pieces || []).map((piece) => {
              const quotedPiece = (quotedConfig?.pieces || []).find(
                (candidate) => candidate.piece_kind === piece.piece_kind
                  && candidate.arm_style === piece.arm_style,
              )
              return quotedPiece ? { ...piece, ...quotedPiece } : piece
            }),
          }
        : quotedConfig
      return {
        ...line,
        workset_config: worksetConfig,
        unit_price: String(quote.unit_price),
        fabric: quote.fabric_label || line.fabric,
        color_name: quote.paint_label || line.color_name,
        quote_status: 'ready',
        price_note: '',
      }
    } catch (err) {
      return {
        ...line,
        unit_price: '',
        quote_status: 'error',
        price_note: err.message || 'محاسبه قیمت ناموفق بود.',
      }
    }
  }

  const confirmPick = async () => {
    if (!picked.length) return
    const candidates = picked.map((p) => lineFromProduct(
      p,
      Number(qtys[p.id] || 1),
      pickModes[p.id] || 'full',
    ))
    const newLines = await Promise.all(candidates.map(quoteLine))
    commitLines([...linesRef.current.filter((l) => l.product_id), ...newLines])
    setPickerOpen(false)
    setSelectedWorkset(null)
    setWorksetProducts([])
    setQtys({})
    setPickModes({})
  }

  const commitLines = (next) => {
    linesRef.current = next
    onChange(next)
  }

  const updateLine = (idx, patch) => {
    commitLines(linesRef.current.map((row, i) => (i === idx ? { ...row, ...patch } : row)))
  }
  const removeLine = (idx) => {
    Object.keys(quoteTimers.current).forEach((key) => {
      clearTimeout(quoteTimers.current[key])
      quoteTokens.current[key] = (quoteTokens.current[key] || 0) + 1
    })
    commitLines(linesRef.current.filter((_, i) => i !== idx))
  }

  const scheduleQuote = (idx, draft, immediate = false) => {
    const token = (quoteTokens.current[idx] || 0) + 1
    quoteTokens.current[idx] = token
    clearTimeout(quoteTimers.current[idx])
    updateLine(idx, { ...draft, quote_status: 'loading', price_note: 'در حال محاسبه قیمت…' })
    quoteTimers.current[idx] = setTimeout(async () => {
      const quoted = await quoteLine(draft)
      if (quoteTokens.current[idx] !== token) return
      const current = linesRef.current[idx]
      if (!current || current.product_id !== draft.product_id) return
      updateLine(idx, quoted)
    }, immediate ? 0 : 320)
  }

  const updateBundlePiece = (idx, line, pieceIdx, patch) => {
    const pieces = (line.workset_config?.pieces || []).map((piece, i) => (
      i === pieceIdx ? { ...piece, ...patch } : piece
    ))
    const draft = {
      ...line,
      sale_mode: 'custom_set',
      configuration_mode: uiMode(line) === 'full' ? 'custom' : uiMode(line),
      workset_config: {
        ...(line.workset_config || {}),
        sale_mode: 'custom_set',
        configuration_mode: uiMode(line) === 'full' ? 'custom' : uiMode(line),
        pieces,
      },
      quote_status: 'loading',
      unit_price: '',
      price_note: 'در حال محاسبه قیمت…',
    }
    scheduleQuote(idx, draft)
  }

  const setLineMode = (idx, line, mode) => {
    const saleMode = mode === 'full' ? 'full_set' : 'custom_set'
    const sourcePieces = mode === 'modular'
      ? (line.workset_config?.pieces || [])
      : (line.catalog_pieces?.length ? line.catalog_pieces : line.workset_config?.pieces || [])
    const currentByKey = new Map((line.workset_config?.pieces || []).map((piece) => [
      `${piece.piece_kind}:${piece.arm_style}`,
      piece,
    ]))
    const pieces = sourcePieces.map((piece) => {
      const current = currentByKey.get(`${piece.piece_kind}:${piece.arm_style}`) || {}
      return {
        ...piece,
        fabric_recipe_id: current.fabric_recipe_id || piece.fabric_recipe_id || '',
        paint_recipe_id: current.paint_recipe_id || piece.paint_recipe_id || '',
      }
    })
    const draft = {
      ...line,
      sale_mode: saleMode,
      configuration_mode: mode,
      unit_price: '',
      workset_config: {
        ...(line.workset_config || {}),
        sale_mode: saleMode,
        configuration_mode: mode,
        pieces,
      },
    }
    scheduleQuote(idx, draft, true)
  }

  const applyFinishToAll = (idx, line, kind, value) => {
    const key = `${kind}_recipe_id`
    const pieces = (line.workset_config?.pieces || []).map((piece) => (
      kind === 'paint' && piece.needs_paint === false
        ? piece
        : { ...piece, [key]: value }
    ))
    const draft = {
      ...line,
      sale_mode: 'custom_set',
      unit_price: '',
      workset_config: {
        ...(line.workset_config || {}),
        sale_mode: 'custom_set',
        configuration_mode: uiMode(line),
        pieces,
      },
    }
    scheduleQuote(idx, draft)
  }

  const grouped = useMemo(() => {
    const map = new Map()
    lines.forEach((line, idx) => {
      const key = line.furniture_workset_name || 'سایر'
      if (!map.has(key)) map.set(key, [])
      map.get(key).push({ line, idx })
    })
    return [...map.entries()]
  }, [lines])

  const total = lines.reduce((s, l) => s + Number(l.unit_price || 0) * Number(l.quantity || 1), 0)
  const paintOptions = [{ value: '', label: 'انتخاب رنگ بدنه…' }, ...paints.map((row) => ({ value: String(row.id), label: recipeLabel(row) }))]
  const fabricOptions = [{ value: '', label: 'انتخاب پارچه…' }, ...fabrics.map((row) => ({ value: String(row.id), label: recipeLabel(row, true) }))]

  return (
    <div className={fromLegacy('product-lines')}>
      {stockSourceLabel ? <p className={fromLegacy('muted small')}>موجودی از: {stockSourceLabel}</p> : null}
      {onSeatCountChange && (
        <Field label="تعداد نفر (دستی)">
          <input
            className={fromLegacy('ltr')}
            type="number"
            min="1"
            value={seatCount}
            onChange={(e) => onSeatCountChange(e.target.value)}
            placeholder="مثلاً ۸"
          />
        </Field>
      )}

      {grouped.map(([name, rows]) => (
        <div key={name}>
          {name !== 'سایر' && <p className={fromLegacy('muted small')}>سرویس: {name}</p>}
          {rows.map(({ line, idx }) => {
            const pieces = line.workset_config?.pieces || []
            const mode = uiMode(line)
            const activePieces = pieces.filter((piece) => Number(piece.quantity || 0) > 0)
            const meters = Number(line.workset_config?.sale_choices?.meters || serviceMeters(pieces))
            const rate = Number(line.workset_config?.sale_choices?.price_per_meter || 0)
            return (
              <div key={idx} className={fromLegacy(`sale-line-card order-builder-line mode-${mode}`)}>
                <div className={fromLegacy('sale-line-head')}>
                  <div>
                    <strong>{line.product_name}</strong>
                    {line.product_model ? <span className={fromLegacy('muted small')}>{line.product_model}</span> : null}
                  </div>
                  <Button type="button" variant="ghost" size="sm" className={fromLegacy('sale-line-remove')} onClick={() => removeLine(idx)}>
                    حذف
                  </Button>
                </div>
                <div className={fromLegacy('sale-line-body')}>
                  {pieces.length > 0 && (
                    <div className={fromLegacy('order-builder')}>
                      <div className={fromLegacy('order-mode-grid')} role="radiogroup" aria-label="نوع سفارش سرویس">
                        {ORDER_MODES.map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            role="radio"
                            aria-checked={mode === option.value}
                            className={fromLegacy(`order-mode-card${mode === option.value ? ' active' : ''}`)}
                            onClick={() => setLineMode(idx, line, option.value)}
                          >
                            <strong>{option.title}</strong>
                            <span>{option.description}</span>
                          </button>
                        ))}
                      </div>

                      {mode === 'full' ? (
                        <div className={fromLegacy('order-locked-specs')}>
                          {lockedSpecs(pieces).map((text) => <span key={text}>{text}</span>)}
                        </div>
                      ) : (
                        <>
                          <div className={fromLegacy('order-finish-all')}>
                            <div>
                              <strong>اعمال مشخصات به همه قطعات</strong>
                              <span className={fromLegacy('muted small')}>بعداً می‌توانید هر قطعه را جدا تغییر دهید.</span>
                            </div>
                            <Field label="پارچه همه">
                              <Select
                                value=""
                                onChange={(value) => applyFinishToAll(idx, line, 'fabric', value)}
                                options={fabricOptions}
                              />
                            </Field>
                            <Field label="رنگ همه">
                              <Select
                                value=""
                                onChange={(value) => applyFinishToAll(idx, line, 'paint', value)}
                                options={paintOptions}
                              />
                            </Field>
                          </div>
                          <div className={fromLegacy('order-piece-grid')}>
                            {pieces.map((piece, pieceIdx) => {
                              const disabled = mode === 'modular' && Number(piece.quantity || 0) === 0
                              return (
                                <div
                                  key={`${piece.piece_kind}-${piece.arm_style}-${pieceIdx}`}
                                  className={fromLegacy(`order-piece-card${disabled ? ' disabled' : ''}`)}
                                >
                                  <div className={fromLegacy('order-piece-head')}>
                                    <strong>{piece.piece_label || 'قطعه'}</strong>
                                    {mode === 'modular' && (
                                      <span className={fromLegacy(disabled ? 'text-danger small' : 'text-success small')}>
                                        {disabled ? 'حذف‌شده' : 'فعال'}
                                      </span>
                                    )}
                                  </div>
                                  <Field label={mode === 'modular' ? 'تعداد قطعه' : 'تعداد ثابت'}>
                                    <input
                                      className={fromLegacy('ltr')}
                                      type="number"
                                      min="0"
                                      value={piece.quantity ?? 1}
                                      disabled={mode !== 'modular'}
                                      onChange={(e) => updateBundlePiece(idx, line, pieceIdx, { quantity: Number(e.target.value) })}
                                    />
                                  </Field>
                                  {!disabled && piece.needs_paint !== false && (
                                    <Field label="رنگ بدنه">
                                      <Select
                                        value={piece.paint_recipe_id ? String(piece.paint_recipe_id) : ''}
                                        onChange={(value) => updateBundlePiece(idx, line, pieceIdx, { paint_recipe_id: value })}
                                        options={paintOptions}
                                      />
                                    </Field>
                                  )}
                                  {!disabled && (
                                    <Field label="پارچه">
                                      <Select
                                        value={piece.fabric_recipe_id ? String(piece.fabric_recipe_id) : ''}
                                        onChange={(value) => updateBundlePiece(idx, line, pieceIdx, { fabric_recipe_id: value })}
                                        options={fabricOptions}
                                      />
                                    </Field>
                                  )}
                                  {mode === 'modular' && (
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => updateBundlePiece(idx, line, pieceIdx, { quantity: disabled ? 1 : 0 })}
                                    >
                                      {disabled ? 'بازگردانی قطعه' : 'حذف از دست'}
                                    </Button>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                          {mode === 'modular' && (
                            <p className={fromLegacy('order-modular-summary')}>
                              {toPersianDigits(activePieces.length)} نوع قطعه فعال · {' '}
                              {toPersianDigits(activePieces.reduce((sum, piece) => sum + Number(piece.quantity || 0), 0))} قطعه در هر سرویس
                            </p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                  <Field label="تعداد سرویس">
                    <input className={fromLegacy('ltr')} type="number" min="1" value={line.quantity} onChange={(e) => updateLine(idx, { quantity: e.target.value })} />
                  </Field>
                  {line.quote_status === 'loading' ? (
                    <p className={fromLegacy('order-quote-state')} aria-live="polite">در حال محاسبه قیمت نهایی…</p>
                  ) : line.price_note ? (
                    <p className={fromLegacy('alert-error')} role="alert">{line.price_note}</p>
                  ) : null}
                  {line.unit_price && meters > 0 && rate > 0 && (
                    <p className={fromLegacy('muted small')}>
                      قیمت نهایی: {formatMoney(Number(line.unit_price) * Number(line.quantity || 1))}
                      {' '}— {toPersianDigits(meters)} متر × {formatMoney(rate)}
                      {Number(line.quantity) > 1 ? ` × ${toPersianDigits(line.quantity)} سرویس` : ''}
                    </p>
                  )}
                  {line.unit_price && !(meters > 0 && rate > 0) && (
                    <p className={fromLegacy('muted small')}>جمع ردیف: {formatMoney(Number(line.unit_price) * Number(line.quantity || 1))}</p>
                  )}
                  {line.target_min_price && Number(line.unit_price) > 0 && Number(line.unit_price) < Number(line.target_min_price) && (
                    <p className={fromLegacy('doc-unbalanced')}>قیمت از حاشیه سود هدف پایین‌تر است.</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ))}

      <div className={fromLegacy('product-lines-toolbar')}>
        <Button type="button" onClick={() => { setSelectedWorkset(null); setSearch(''); setPickerOpen(true) }}>
          {lines.length ? 'از سرویس دیگر' : 'انتخاب سرویس'}
        </Button>
      </div>
      {lines.length > 0 && <p className={fromLegacy('muted')}>جمع محصولات: {formatMoney(total)}</p>}

      <Modal
        title={selectedWorkset ? `محصول‌های ${selectedWorkset.name}` : 'انتخاب سرویس'}
        open={pickerOpen}
        onClose={() => { setPickerOpen(false); setSelectedWorkset(null) }}
        wide
      >
        {!selectedWorkset ? (
          <div className={fromLegacy('product-picker')}>
            <input
              className={fromLegacy('search-input')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجوی سرویس…"
            />
            {loading ? (
              <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
            ) : worksets.length === 0 ? (
              <p className={fromLegacy('muted')}>سرویسی یافت نشد.</p>
            ) : (
              <div className={fromLegacy('product-picker-grid')}>
                {worksets.map((w) => (
                  <button
                    key={w.id}
                    type="button"
                    className={fromLegacy('product-picker-item')}
                    onClick={() => openWorkset(w)}
                  >
                    <strong>{w.name}</strong>
                    <span className={fromLegacy('muted small')}>{toPersianDigits(w.piece_count || 0)} قطعه</span>
                    {(w.pieces || []).length > 0 && (
                      <span className={fromLegacy('muted small')}>
                        {(w.pieces || []).map((piece) => `${toPersianDigits(piece.quantity)}× ${piece.piece_label}`).join('، ')}
                      </span>
                    )}
                    {w.seat_count ? <span className={fromLegacy('muted small')}>{toPersianDigits(w.seat_count)} نفر</span> : null}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className={fromLegacy('product-picker')}>
            <button type="button" className={fromLegacy('link')} onClick={() => setSelectedWorkset(null)}>← سرویس‌های دیگر</button>
            {selectedWorkset.pieces?.length > 0 && (
              <p className={fromLegacy('muted small')}>
                ترکیب سرویس: {selectedWorkset.pieces.map((piece) => `${toPersianDigits(piece.quantity)}× ${piece.piece_label}`).join('، ')}
              </p>
            )}
            <input
              className={fromLegacy('search-input')}
              value={productSearch}
              onChange={(e) => { setProductSearch(e.target.value); setProductLimit(24) }}
              placeholder="جستجوی محصول در این سرویس…"
            />
            {loading ? (
              <p className={fromLegacy('muted')}>در حال بارگذاری…</p>
            ) : filteredProducts.length === 0 ? (
              <p className={fromLegacy('muted')}>
                {worksetProducts.length ? 'محصولی با این جستجو پیدا نشد.' : 'برای این سرویس محصولی تعریف نشده.'}
              </p>
            ) : (
              <div className={fromLegacy('product-picker-grid')}>
                {visibleProducts.map((p) => {
                  const pieces = jobPieces(p)
                  const price = catalogPrice(p)
                  const missing = missingMeterPieces(pieces)
                  return (
                    <div key={p.id} className={fromLegacy('product-picker-item')}>
                      <strong>{p.name}</strong>
                      <span className={fromLegacy('muted')}>{pieceSummary(p)}</span>
                      {pieces.length > 0 ? (
                        <>
                          {lockedSpecs(pieces).map((text) => <span key={text} className={fromLegacy('muted small')}>{text}</span>)}
                          {missing.length > 0 && <span className={fromLegacy('alert-error')}>متراژ مصرف ناقص است</span>}
                        </>
                      ) : fabricSummary(p) ? <span className={fromLegacy('muted small')}>پارچه: {fabricSummary(p)}</span> : null}
                      {!pieces.length && (price > 0 ? (
                        <span>{formatMoney(price)}</span>
                      ) : (
                        <span className={fromLegacy('alert-error')}>بدون قیمت</span>
                      ))}
                      <Field label="تعداد سرویس">
                        <input
                          className={fromLegacy('ltr')}
                          type="number"
                          min="0"
                          value={qtys[p.id] || 0}
                          onChange={(e) => setQtys((q) => ({ ...q, [p.id]: e.target.value }))}
                          disabled={!canAdd(p)}
                        />
                      </Field>
                      {pieces.length > 0 && (
                        <div className={fromLegacy('product-picker-modes')}>
                          {ORDER_MODES.map((mode) => (
                            <button
                              key={mode.value}
                              type="button"
                              className={fromLegacy(`product-picker-mode${pickModes[p.id] === mode.value ? ' active' : ''}`)}
                              onClick={() => {
                                setPickModes((m) => ({ ...m, [p.id]: mode.value }))
                                setQtys((q) => ({ ...q, [p.id]: Number(q[p.id] || 1) }))
                              }}
                            >
                              {mode.title}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            {visibleProducts.length < filteredProducts.length && (
              <Button type="button" variant="ghost" onClick={() => setProductLimit((limit) => limit + 24)}>
                نمایش محصولات بیشتر ({toPersianDigits(filteredProducts.length - visibleProducts.length)})
              </Button>
            )}
            {picked.length > 0 && (
              <p className={fromLegacy('muted')}>
                {pickTotal > 0 ? `جمع قیمت کاتالوگ: ${formatMoney(pickTotal)} — ` : ''}
                {toPersianDigits(picked.length)} محصول
              </p>
            )}
            <div className={fromLegacy('form-actions')}>
              <Button type="button" variant="ghost" onClick={() => { setPickerOpen(false); setSelectedWorkset(null) }}>انصراف</Button>
              <Button type="button" onClick={confirmPick} disabled={!picked.length}>
                افزودن به فاکتور
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

export { EMPTY_LINE as EMPTY_PRODUCT_LINE }
