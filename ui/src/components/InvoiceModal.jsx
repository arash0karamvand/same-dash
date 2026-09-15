import { useMemo, useRef, useState } from 'react'
import { salesApi } from '../api/client'
import { Button, Modal } from './ui'
import { buildInvoiceHtml } from '../utils/printInvoice'
import { fromLegacy } from '../styles/tw.js'

export default function InvoiceModal({ sale, open, onClose }) {
  const iframeRef = useRef(null)
  const [excelLoading, setExcelLoading] = useState(false)
  const html = useMemo(() => (sale ? buildInvoiceHtml(sale) : ''), [sale])

  const handlePrint = () => {
    const win = iframeRef.current?.contentWindow
    if (!win) return
    win.focus()
    win.print()
  }

  const handleExcel = async () => {
    if (!sale?.id) return
    setExcelLoading(true)
    try {
      await salesApi.exportExcel(sale.id)
    } catch (err) {
      window.alert(err.message || 'خطا در دریافت اکسل')
    } finally {
      setExcelLoading(false)
    }
  }

  return (
    <Modal title={sale ? `فاکتور ${sale.invoice_number || sale.id}` : 'فاکتور'} open={open} onClose={onClose} wide>
      <div className={fromLegacy("invoice-modal-toolbar")}>
        <Button type="button" onClick={handlePrint}>چاپ / ذخیره PDF</Button>
        <Button type="button" variant="ghost" onClick={handleExcel} disabled={excelLoading || !sale?.id}>
          {excelLoading ? 'در حال آماده‌سازی…' : 'دانلود اکسل'}
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>بستن</Button>
      </div>
      {html ? (
        <iframe
          ref={iframeRef}
          title="پیش‌نمایش فاکتور"
          className={fromLegacy("invoice-preview-frame")}
          srcDoc={html}
        />
      ) : (
        <p className={fromLegacy("muted")}>فاکتور در دسترس نیست.</p>
      )}
    </Modal>
  )
}
