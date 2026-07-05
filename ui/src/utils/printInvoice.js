import { formatDate, formatMoney, formatNumber } from './format'
import { todayIso } from './jalali'

const PAYMENT_LABELS = {
  cash: 'نقدی',
  card: 'کارت‌خوان',
  online: 'آنلاین',
  credit: 'اعتباری',
  check: 'چک',
}

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function displayLineItems(sale) {
  if (sale.line_items?.length) return sale.line_items
  const amount = Number(sale.amount) || Number(sale.final_amount) || 0
  return [
    {
      product_name: sale.description?.trim() || 'فروش',
      quantity: 1,
      unit_price: amount,
      line_total: amount,
    },
  ]
}

function lineItemsHtml(sale) {
  return displayLineItems(sale)
    .map(
      (item) => `
    <tr>
      <td>${escapeHtml(item.product_name)}</td>
      <td class="num">${formatNumber(item.quantity)}</td>
      <td class="num">${formatMoney(item.unit_price)}</td>
      <td class="num">${formatMoney(item.line_total)}</td>
    </tr>`,
    )
    .join('')
}

function installmentsHtml(items) {
  if (!items?.length) return ''
  const rows = items
    .map(
      (inst, i) => `
    <tr>
      <td>${i + 1}</td>
      <td class="num">${formatMoney(inst.amount)}</td>
      <td>${escapeHtml(formatDate(inst.due_date))}</td>
      <td class="ltr">${escapeHtml(inst.check_number || '—')}</td>
      <td>${escapeHtml(inst.bank_name || '—')}</td>
      <td>${escapeHtml(inst.notes || '—')}</td>
      <td>${escapeHtml(inst.status_display || inst.status || '—')}</td>
    </tr>`,
    )
    .join('')
  return `
    <h3>چک‌ها و اقساط</h3>
    <table>
      <thead>
        <tr>
          <th>#</th><th>مبلغ</th><th>سررسید</th><th>شماره چک</th><th>بانک</th><th>توضیحات</th><th>وضعیت</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`
}

export function buildInvoiceHtml(sale) {
  if (!sale) return ''

  const invoiceNo = sale.invoice_number || `#${sale.id}`
  const payLabel = PAYMENT_LABELS[sale.payment_method] || sale.payment_method_display || '—'
  const sellerLabel = sale.seller_name || sale.recorded_by || '—'

  return `<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>فاکتور ${escapeHtml(invoiceNo)}</title>
  <style>
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      padding: 0;
      background: #fff;
    }
    body {
      font-family: Tahoma, 'Segoe UI', Arial, sans-serif;
      padding: 20px 24px 32px;
      color: #0f172a;
      line-height: 1.65;
      font-size: 14px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      border-bottom: 2px solid #6366f1;
      padding-bottom: 14px;
      margin-bottom: 18px;
    }
    .brand { font-size: 24px; font-weight: 700; color: #6366f1; margin-bottom: 4px; }
    .meta { text-align: left; font-size: 13px; color: #475569; line-height: 1.8; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 18px;
    }
    .box {
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      padding: 12px 14px;
      background: #f8fafc;
    }
    .box h4 { margin: 0 0 8px; font-size: 12px; color: #64748b; font-weight: 600; }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0 18px;
      font-size: 13px;
    }
    th, td {
      border: 1px solid #dbe3ee;
      padding: 8px 10px;
      text-align: right;
      vertical-align: top;
    }
    th { background: #f1f5f9; font-weight: 600; }
    .num { direction: ltr; text-align: left; white-space: nowrap; }
    .ltr { direction: ltr; text-align: left; }
    .totals {
      width: 100%;
      max-width: 380px;
      margin-right: 0;
      margin-left: auto;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      overflow: hidden;
    }
    .totals div {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 9px 14px;
      border-bottom: 1px solid #eef2f7;
    }
    .totals div:last-child { border-bottom: none; }
    .totals .final {
      font-weight: 700;
      font-size: 15px;
      background: #f8fafc;
    }
    .muted { color: #64748b; }
    h3 { font-size: 15px; margin: 18px 0 8px; }
    .footer {
      margin-top: 28px;
      padding-top: 12px;
      border-top: 1px solid #e2e8f0;
      font-size: 12px;
      color: #64748b;
      text-align: center;
    }
    .notes {
      margin-top: 16px;
      padding: 12px 14px;
      background: #f8fafc;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
    }
    @media print {
      body { padding: 8mm; }
      .no-print { display: none !important; }
    }
    @media (max-width: 640px) {
      .grid { grid-template-columns: 1fr; }
      .header { flex-direction: column; }
      .meta { text-align: right; }
    }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="brand">سام اکسون</div>
      <div class="muted">فاکتور فروش — شماره: <strong>${escapeHtml(invoiceNo)}</strong></div>
    </div>
    <div class="meta">
      <div>تاریخ: ${escapeHtml(formatDate(sale.sold_at))}</div>
      <div>شعبه: ${escapeHtml(sale.branch_label || '—')}</div>
      <div>فروشنده: ${escapeHtml(sellerLabel)}</div>
    </div>
  </div>

  <div class="grid">
    <div class="box">
      <h4>مشتری</h4>
      <div><strong>${escapeHtml(sale.customer_name || '—')}</strong></div>
      ${sale.customer_phone ? `<div class="ltr">${escapeHtml(sale.customer_phone)}</div>` : ''}
    </div>
    <div class="box">
      <h4>پرداخت</h4>
      <div>وضعیت: ${escapeHtml(sale.payment_status_display || '—')}</div>
      <div>روش: ${escapeHtml(payLabel)}</div>
    </div>
  </div>

  <h3>اقلام فاکتور</h3>
  <table>
    <thead>
      <tr><th>شرح</th><th>تعداد</th><th>قیمت واحد</th><th>جمع</th></tr>
    </thead>
    <tbody>${lineItemsHtml(sale)}</tbody>
  </table>

  <div class="totals">
    <div><span>جمع اقلام</span><span class="num">${formatMoney(sale.amount)}</span></div>
    <div><span>تخفیف${sale.discount_type_display ? ` (${escapeHtml(sale.discount_type_display)})` : ''}</span><span class="num">${formatMoney(sale.discount)}</span></div>
    <div class="final"><span>مبلغ نهایی</span><span class="num">${formatMoney(sale.final_amount)}</span></div>
    <div><span>پرداخت‌شده</span><span class="num">${formatMoney(sale.paid_amount)}</span></div>
    <div><span>مانده</span><span class="num">${formatMoney(sale.balance_due)}</span></div>
  </div>

  ${installmentsHtml(sale.installments)}

  ${sale.description ? `<div class="notes"><h3 style="margin:0 0 6px;font-size:14px">توضیحات</h3><p style="margin:0">${escapeHtml(sale.description)}</p></div>` : ''}

  <div class="footer">صادر شده از سام اکسون — ${escapeHtml(formatDate(todayIso()))}</div>
</body>
</html>`
}

export function printHtmlInIframe(html) {
  const iframe = document.createElement('iframe')
  iframe.setAttribute('title', 'invoice-print')
  iframe.style.position = 'fixed'
  iframe.style.top = '0'
  iframe.style.left = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = 'none'
  document.body.appendChild(iframe)

  const doc = iframe.contentDocument || iframe.contentWindow?.document
  if (!doc) {
    document.body.removeChild(iframe)
    throw new Error('چاپ فاکتور در این مرورگر پشتیبانی نمی‌شود.')
  }

  doc.open()
  doc.write(html)
  doc.close()

  const win = iframe.contentWindow
  const cleanup = () => {
    setTimeout(() => {
      if (iframe.parentNode) iframe.parentNode.removeChild(iframe)
    }, 500)
  }

  win.onload = () => {
    win.focus()
    win.print()
    cleanup()
  }

  // fallback if onload already fired
  setTimeout(() => {
    if (iframe.parentNode) {
      win.focus()
      win.print()
      cleanup()
    }
  }, 400)
}

export function printSaleInvoice(sale) {
  const html = buildInvoiceHtml(sale)
  if (!html) throw new Error('اطلاعات فاکتور نامعتبر است.')

  const blob = new Blob(['\ufeff', html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank')

  if (win) {
    win.addEventListener('load', () => URL.revokeObjectURL(url), { once: true })
    return
  }

  URL.revokeObjectURL(url)
  printHtmlInIframe(html)
}
