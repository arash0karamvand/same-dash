import { useEffect, useState } from 'react'
import { procurementApi } from '../api/client'
import { Badge, Button, Card, EmptyState, Field } from '../components/ui'
import { tw } from '../styles/tw'

const EMPTY = {
  material_id: '',
  quantity: '',
  source_type: 'manual',
  source_key: '',
  warehouse_id: '',
  note: '',
}

export default function Procurement() {
  const [requests, setRequests] = useState([])
  const [orders, setOrders] = useState([])
  const [receipts, setReceipts] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [requestData, orderData, receiptData] = await Promise.all([
        procurementApi.requests(),
        procurementApi.orders(),
        procurementApi.receipts(),
      ])
      setRequests(requestData.results || [])
      setOrders(orderData.results || [])
      setReceipts(receiptData.results || [])
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const generate = async (event) => {
    event.preventDefault()
    try {
      await procurementApi.generateShortages({
        destination: {
          kind: 'warehouse',
          ...(form.warehouse_id ? { warehouse_id: Number(form.warehouse_id) } : {}),
        },
        note: form.note,
        requirements: [{
          material_id: Number(form.material_id),
          quantity: form.quantity,
          source_type: form.source_type,
          source_key: form.source_key,
        }],
      })
      setForm(EMPTY)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const approveRequest = async (row) => {
    const supplierId = window.prompt('شناسه تامین‌کننده را وارد کنید')
    if (!supplierId) return
    const prices = {}
    for (const line of row.lines) {
      const price = window.prompt(`قیمت واحد ${line.material}`, '0')
      if (price == null) return
      prices[String(line.id)] = Number(price)
    }
    try {
      await procurementApi.approveRequest(row.uuid, { supplier_id: Number(supplierId), prices })
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const receive = async (order) => {
    const open = order.lines.filter((line) => line.remaining_quantity > 0)
    if (!open.length) return
    const receiptNumber = window.prompt('شماره رسید انبار')
    const invoiceNumber = window.prompt('شماره فاکتور')
    if (!receiptNumber || !invoiceNumber) return
    const lines = []
    for (const line of open) {
      const quantity = window.prompt(`مقدار دریافتی ${line.material}`, String(line.remaining_quantity))
      if (!quantity) continue
      const unitPrice = window.prompt(`قیمت واحد ${line.material}`, String(line.unit_price))
      if (unitPrice == null) return
      const payload = {
        order_line_id: line.id,
        expected_quantity: Number(quantity),
        received_quantity: Number(quantity),
        unit_price: Number(unitPrice),
      }
      if (Number(unitPrice) !== Number(line.unit_price)) {
        payload.price_variance_reason = window.prompt('علت اختلاف قیمت') || ''
      }
      lines.push(payload)
    }
    if (!lines.length) return
    try {
      await procurementApi.receiveOrder(order.uuid, {
        receipt_number: receiptNumber,
        invoice_number: invoiceNumber,
        lines,
      })
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const uploadDocument = async (receipt, file) => {
    if (!file) return
    try {
      await procurementApi.uploadReceiptDocument(receipt.id, file, 'تصویر فاکتور خرید')
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const approveReceipt = async (receipt) => {
    try {
      await procurementApi.approveReceipt(receipt.uuid)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className={tw.page}>
      <div>
        <h1>تدارکات و خرید</h1>
        <p className={tw.muted}>کسری مواد، سفارش خرید، رسید و ردیابی بهای موجودی در یک گردش واحد</p>
      </div>

      {error && <div className={tw.alert}>{error}</div>}

      <Card title="تولید درخواست از کسری">
        <form className={tw.formGrid} onSubmit={generate}>
          <Field label="شناسه متریال">
            <input type="number" min="1" required value={form.material_id}
              onChange={(e) => setForm({ ...form, material_id: e.target.value })} />
          </Field>
          <Field label="مقدار موردنیاز">
            <input type="number" min="0.001" step="0.001" required value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </Field>
          <Field label="نوع منبع تقاضا">
            <input required value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })} />
          </Field>
          <Field label="کلید یکتای منبع">
            <input required value={form.source_key}
              onChange={(e) => setForm({ ...form, source_key: e.target.value })} />
          </Field>
          <Field label="شناسه انبار (اختیاری)">
            <input type="number" min="1" value={form.warehouse_id}
              onChange={(e) => setForm({ ...form, warehouse_id: e.target.value })} />
          </Field>
          <Field label="توضیح">
            <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </Field>
          <Button type="submit">محاسبه و ثبت کسری</Button>
        </form>
      </Card>

      <Card title="درخواست‌های خرید">
        {!loading && !requests.length ? <EmptyState title="درخواستی ثبت نشده است" /> : (
          <div className={tw.tableWrap}>
            <table className={tw.table}>
              <thead><tr><th>شناسه</th><th>وضعیت</th><th>تقاضاها</th><th>عملیات</th></tr></thead>
              <tbody>{requests.map((row) => (
                <tr key={row.uuid}>
                  <td>{row.uuid.slice(0, 8)}</td>
                  <td><Badge>{row.status}</Badge></td>
                  <td>{row.lines.map((line) => `${line.material}: ${line.quantity}`).join('، ')}</td>
                  <td>{row.status === 'draft' && <Button size="sm" onClick={() => approveRequest(row)}>تایید و سفارش</Button>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="سفارش‌های خرید">
        <div className={tw.tableWrap}>
          <table className={tw.table}>
            <thead><tr><th>سفارش</th><th>تامین‌کننده</th><th>وضعیت</th><th>مانده</th><th>عملیات</th></tr></thead>
            <tbody>{orders.map((row) => (
              <tr key={row.uuid}>
                <td>{row.uuid.slice(0, 8)}</td><td>{row.supplier}</td><td><Badge>{row.status}</Badge></td>
                <td>{row.lines.map((line) => `${line.material}: ${line.remaining_quantity}`).join('، ')}</td>
                <td>{['approved', 'partial'].includes(row.status) && <Button size="sm" onClick={() => receive(row)}>ثبت رسید</Button>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Card>

      <Card title="رسیدهای کالا">
        <div className={tw.tableWrap}>
          <table className={tw.table}>
            <thead><tr><th>رسید / فاکتور</th><th>وضعیت</th><th>مقدار</th><th>سند فاکتور</th><th>عملیات</th></tr></thead>
            <tbody>{receipts.map((row) => (
              <tr key={row.uuid}>
                <td>{row.receipt_number} / {row.invoice_number}</td>
                <td><Badge>{row.status}</Badge></td>
                <td>{row.lines.map((line) => `${line.material}: ${line.received_quantity}`).join('، ')}</td>
                <td>
                  {row.has_attachment ? 'ثبت شده' : (
                    <input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp"
                      onChange={(e) => uploadDocument(row, e.target.files?.[0])} />
                  )}
                </td>
                <td>{row.status === 'draft' && <Button size="sm" disabled={!row.has_attachment}
                  onClick={() => approveReceipt(row)}>تایید نهایی</Button>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
