// کامپوننت نمایش سندهای حسابداری مرتبط با فاکتور
import { useState, useEffect } from 'react'
import { Card } from './ui'
import { formatDate, formatMoney } from '../utils/format'

export default function SaleJournals({ saleId }) {
  const [journals, setJournals] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (saleId) {
      loadJournals()
    }
  }, [saleId])

  const loadJournals = async () => {
    try {
      const response = await fetch(`/api/sales/${saleId}/journals/`)
      const data = await response.json()
      if (data.success) {
        setJournals(data.results || [])
      }
    } catch (error) {
      console.error('خطا در بارگذاری سندها:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="text-sm text-gray-500 p-2">در حال بارگذاری سندها...</div>

  if (journals.length === 0) {
    return <div className="text-sm text-gray-500 p-2">هیچ سند حسابداری ثبت نشده است.</div>
  }

  return (
    <div className="space-y-3" dir="rtl">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">سندهای حسابداری مرتبط</h3>
      {journals.map((journal) => (
        <Card key={journal.id} className="p-3 bg-gray-50 border border-gray-200">
          <div className="flex justify-between items-start mb-2">
            <div>
              <span className="text-sm font-medium">سند شماره: {journal.document_number}</span>
              <span className={`mr-2 px-2 py-1 text-xs rounded ${
                journal.is_approved ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
              }`}>
                {journal.is_approved ? 'تایید شده' : 'پیش‌نویس'}
              </span>
            </div>
            <span className="text-xs text-gray-500">{formatDate(journal.entry_date)}</span>
          </div>
          
          <p className="text-xs text-gray-600 mb-2">{journal.description}</p>
          
          {journal.lines && journal.lines.length > 0 && (
            <div className="text-xs space-y-1">
              <div className="font-medium text-gray-700 mb-1">سطرهای سند:</div>
              {journal.lines.map((line, idx) => (
                <div key={idx} className="flex justify-between text-gray-600 pr-2">
                  <span>{line.account_name}</span>
                  <div>
                    {line.debit > 0 && <span className="text-blue-600">بدهکار: {formatMoney(line.debit)}</span>}
                    {line.credit > 0 && <span className="text-green-600">بستانکار: {formatMoney(line.credit)}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
          
          <div className="mt-2 text-xs text-gray-500">
            دفتر: {journal.ledger_label} | نوع: {journal.entry_type_label}
          </div>
        </Card>
      ))}
    </div>
  )
}
