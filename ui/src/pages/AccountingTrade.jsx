import { useEffect, useState } from 'react'
import { accountingApi, materialsApi } from '../api/client'
import { resultList } from '../api/accounting'
import {
  AccountingDataPanel,
  AccountingPageHeader,
  AccountingToolbar,
} from '../components/accounting/AccountingERP'
import { Button, Field } from '../components/ui'
import { formatRial } from '../utils/format'
import { fromLegacy } from '../styles/tw'

const EMPTY = {
  material_id: '',
  quantity: '',
  unit_price: '',
  trade_discount: '',
  freight: '',
  insurance: '',
  other_cost: '',
  vat_rate: '10',
  settlement: 'credit',
  invoice_number: '',
  warehouse_receipt: '',
  description: '',
}

export default function AccountingTrade() {
  const [form, setForm] = useState(EMPTY)
  const [materials, setMaterials] = useState([])
  const [documents, setDocuments] = useState([])
  const [card, setCard] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async () => {
    const [materialPayload, tradePayload] = await Promise.all([
      materialsApi.list({ limit: 200, approved_only: true }),
      accountingApi.tradeDocuments(),
    ])
    const rows = resultList(materialPayload)
    setMaterials(rows.length ? rows : (materialPayload?.results || []))
    setDocuments(tradePayload?.results || [])
  }

  useEffect(() => {
    const timer = setTimeout(() => {
      load().catch((err) => setError(err.message || 'فهرست کالا بارگذاری نشد.'))
    }, 0)
    return () => clearTimeout(timer)
  }, [])

  const set = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }))

  const submit = async (action) => {
    setError('')
    setNotice('')
    const payload = {
      ...form,
      material_id: Number(form.material_id),
      document_id: Number(form.document_id || 0) || undefined,
      amount: form.cash_discount,
    }
    try {
      const created = await action(payload)
      setNotice(`سند ${created.document_code || created.kind_label} ثبت شد.`)
      if (created.warning) setNotice((prev) => `${prev} ${created.warning}`)
      await load()
      if (form.material_id) setCard(await accountingApi.tradeKardex(form.material_id))
    } catch (err) {
      setError(err.message || 'ثبت انجام نشد.')
    }
  }

  const openCard = async (materialId) => {
    setError('')
    try {
      setCard(await accountingApi.tradeKardex(materialId))
    } catch (err) {
      setError(err.message || 'کارت حساب بارگذاری نشد.')
    }
  }

  return (
    <div className={fromLegacy('acct-erp-page')}>
      <AccountingPageHeader
        eyebrow="سیستم دائمی"
        title="خرید و فروش کالا"
        description="بهای تمام‌شده برابر قیمت پس از تخفیف تجاری به‌علاوه حمل، بیمه و سایر مخارج است. مالیات بر ارزش افزوده جدا ثبت می‌شود. تخفیف نقدی موقع پرداخت زودهنگام اعمال می‌شود."
      />
      {error && <p className={fromLegacy('form-error')}>{error}</p>}
      {notice && <p>{notice}</p>}
      <AccountingDataPanel title="صدور سند">
        <div className={fromLegacy('acct-erp-toolbar')}>
          <Field label="کالا">
            <select className="acct-input" value={form.material_id} onChange={set('material_id')} tabIndex={0}>
              <option value="">انتخاب کالا</option>
              {materials.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </select>
          </Field>
          <Field label="تعداد"><input className="acct-input acct-input--numeric" value={form.quantity} onChange={set('quantity')} inputMode="decimal" tabIndex={0} /></Field>
          <Field label="نرخ"><input className="acct-input acct-input--numeric" value={form.unit_price} onChange={set('unit_price')} inputMode="numeric" tabIndex={0} /></Field>
          <Field label="تخفیف تجاری"><input className="acct-input acct-input--numeric" value={form.trade_discount} onChange={set('trade_discount')} inputMode="numeric" tabIndex={0} /></Field>
          <Field label="حمل"><input className="acct-input acct-input--numeric" value={form.freight} onChange={set('freight')} inputMode="numeric" tabIndex={0} /></Field>
          <Field label="بیمه"><input className="acct-input acct-input--numeric" value={form.insurance} onChange={set('insurance')} inputMode="numeric" tabIndex={0} /></Field>
          <Field label="سایر مخارج"><input className="acct-input acct-input--numeric" value={form.other_cost} onChange={set('other_cost')} inputMode="numeric" tabIndex={0} /></Field>
          <Field label="نرخ مالیات"><input className="acct-input acct-input--numeric" value={form.vat_rate} onChange={set('vat_rate')} inputMode="decimal" tabIndex={0} /></Field>
          <Field label="تسویه">
            <select value={form.settlement} onChange={set('settlement')}>
              <option value="credit">نسیه</option>
              <option value="cash">نقد</option>
            </select>
          </Field>
          <Field label="شماره فاکتور"><input value={form.invoice_number} onChange={set('invoice_number')} /></Field>
          <Field label="رسید انبار"><input value={form.warehouse_receipt} onChange={set('warehouse_receipt')} /></Field>
        </div>
        <AccountingToolbar>
          <Button type="button" onClick={() => submit(accountingApi.tradePurchase)}>ثبت خرید</Button>
          <Button type="button" variant="ghost" onClick={() => submit(accountingApi.tradeSale)}>ثبت فروش</Button>
          <Button type="button" variant="ghost" onClick={() => openCard(form.material_id)} disabled={!form.material_id}>کارت حساب</Button>
        </AccountingToolbar>
      </AccountingDataPanel>
      <AccountingDataPanel title="اسناد" subtitle="برگشت و تخفیف نقدی روی سند مبنا انجام می‌شود.">
        <div className="acct-card-stack is-compact">
          {documents.map((doc) => (
            <article key={doc.id} className="acct-doc-card">
              <div className="acct-doc-id">
                <strong className="acct-number">{doc.document_code}</strong>
                <small>{doc.kind_label}</small>
              </div>
              <div className="acct-doc-copy">
                <span>{doc.material_name}</span>
                <p>فاکتور {doc.invoice_number || '—'} · مانده تعداد {doc.remaining_qty}</p>
              </div>
              <div className="acct-doc-amounts">
                <div>
                  <span>بهای موجودی</span>
                  <strong className="acct-number">{formatRial(doc.inventory_amount)}</strong>
                </div>
                <div>
                  <span>مالیات</span>
                  <strong className="acct-number">{formatRial(doc.vat_amount)}</strong>
                </div>
              </div>
              <div className="acct-doc-actions">
                {doc.kind === 'purchase' && (
                  <>
                    <Button type="button" variant="ghost" onClick={() => submitReturn(doc, accountingApi.tradePurchaseReturn)}>برگشت</Button>
                    {doc.settlement === 'credit' && (
                      <Button type="button" variant="ghost" onClick={() => submitDiscount(doc)}>تخفیف نقدی</Button>
                    )}
                  </>
                )}
                {doc.kind === 'sale' && (
                  <Button type="button" variant="ghost" onClick={() => submitReturn(doc, accountingApi.tradeSaleReturn)}>برگشت</Button>
                )}
              </div>
            </article>
          ))}
        </div>
      </AccountingDataPanel>
      {card && (
        <AccountingDataPanel title={`کارت حساب ${card.material_name}`} subtitle={card.warning || `موجودی ${card.stock}`}>
          <div className="acct-card-stack is-compact">
            {card.lines.map((line, index) => (
              <div key={`${line.reference}-${index}`} className="acct-line-card">
                <div>{line.reason}</div>
                <span className="acct-number acct-credit">{line.in_qty || '—'}</span>
                <span className="acct-number acct-debit">{line.out_qty || '—'}</span>
                <strong className="acct-number">{formatRial(line.unit_cost)}</strong>
                <strong className="acct-number">{formatRial(line.balance_value)}</strong>
              </div>
            ))}
          </div>
          <p>تعدیل تخفیف نقدی روی بهای موجودی: {formatRial(card.discount_adjustments)} — مانده پس از تعدیل: {formatRial(card.balance_value)}</p>
        </AccountingDataPanel>
      )}
    </div>
  )

  async function submitReturn(doc, action) {
    const quantity = window.prompt('تعداد برگشت', String(doc.remaining_qty))
    if (!quantity) return
    const warehouse = doc.kind === 'purchase' ? window.prompt('شماره رسید برگشت انبار', '') : ''
    if (doc.kind === 'purchase' && !warehouse) return
    setError('')
    try {
      const created = await action({
        document_id: doc.id,
        quantity,
        invoice_number: `R-${doc.invoice_number}`,
        warehouse_receipt: warehouse || '',
      })
      setNotice(`برگشت با سند ${created.document_code} ثبت شد.`)
      await load()
    } catch (err) {
      setError(err.message || 'برگشت ثبت نشد.')
    }
  }

  async function submitDiscount(doc) {
    const amount = window.prompt('مبلغ تخفیف نقدی', '')
    if (!amount) return
    setError('')
    try {
      const created = await accountingApi.tradeDiscount({ document_id: doc.id, amount })
      setNotice(`تخفیف نقدی با سند ${created.document_code} ثبت شد.`)
      await load()
    } catch (err) {
      setError(err.message || 'تخفیف ثبت نشد.')
    }
  }
}
