import { useMemo, useRef } from 'react'
import { Button, Modal } from './ui'
import { buildInvoiceHtml } from '../utils/printInvoice'

export default function InvoiceModal({ sale, open, onClose }) {
  const iframeRef = useRef(null)
  const html = useMemo(() => (sale ? buildInvoiceHtml(sale) : ''), [sale])

  const handlePrint = () => {
    const win = iframeRef.current?.contentWindow
    if (!win) return
    win.focus()
    win.print()
  }

  return (
    <Modal title={sale ? `فاکتور ${sale.invoice_number || sale.id}` : 'فاکتور'} open={open} onClose={onClose} wide>
      <div className="invoice-modal-toolbar">
        <Button type="button" onClick={handlePrint}>چاپ / ذخیره PDF</Button>
        <Button type="button" variant="ghost" onClick={onClose}>بستن</Button>
      </div>
      {html ? (
        <iframe
          ref={iframeRef}
          title="پیش‌نمایش فاکتور"
          className="invoice-preview-frame"
          srcDoc={html}
        />
      ) : (
        <p className="muted">فاکتور در دسترس نیست.</p>
      )}
    </Modal>
  )
}
