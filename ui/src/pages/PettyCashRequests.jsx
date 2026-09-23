import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui'

export default function PettyCashRequests() {
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    amount: '',
    purpose: '',
    notes: ''
  })

  useEffect(() => {
    loadRequests()
  }, [])

  const loadRequests = async () => {
    try {
      const response = await fetch('/api/office-forms/petty-cash/')
      const data = await response.json()
      if (data.success) {
        setRequests(data.results)
      }
    } catch (error) {
      console.error('خطا در بارگذاری:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const response = await fetch('/api/office-forms/petty-cash/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      const data = await response.json()
      if (data.success) {
        setShowForm(false)
        setFormData({ amount: '', purpose: '', notes: '' })
        loadRequests()
      }
    } catch (error) {
      console.error('خطا در ثبت:', error)
    }
  }

  const downloadExcel = (id) => {
    window.location.href = `/api/office-forms/petty-cash/${id}/export-excel/`
  }

  const getStatusColor = (status) => {
    const colors = {
      pending: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      paid: 'bg-blue-100 text-blue-800',
      settled: 'bg-purple-100 text-purple-800'
    }
    return colors[status] || 'bg-gray-100'
  }

  if (loading) return <div className="p-8">در حال بارگذاری...</div>

  return (
    <div className="container mx-auto p-6" dir="rtl">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>درخواست‌های تنخواه</CardTitle>
            <button
              onClick={() => setShowForm(!showForm)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              {showForm ? 'لغو' : '+ درخواست جدید'}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {showForm && (
            <form onSubmit={handleSubmit} className="mb-6 p-4 border rounded-lg bg-gray-50">
              <div className="grid gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">مبلغ (ریال)</label>
                  <input
                    type="number"
                    required
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">منظور</label>
                  <textarea
                    required
                    value={formData.purpose}
                    onChange={(e) => setFormData({ ...formData, purpose: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                    rows="3"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">توضیحات</label>
                  <textarea
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                    rows="2"
                  />
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700">
                  ثبت درخواست
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 bg-gray-300 rounded-md hover:bg-gray-400"
                >
                  انصراف
                </button>
              </div>
            </form>
          )}

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">کد</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">درخواست‌کننده</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">مبلغ</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">منظور</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">وضعیت</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">عملیات</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {requests.map((req) => (
                  <tr key={req.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium">{req.reference_code}</td>
                    <td className="px-6 py-4 text-sm">{req.requester_name}</td>
                    <td className="px-6 py-4 text-sm">{parseInt(req.amount).toLocaleString()} ریال</td>
                    <td className="px-6 py-4 text-sm max-w-xs truncate">{req.purpose}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(req.status)}`}>
                        {req.status_label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <button onClick={() => downloadExcel(req.id)} className="text-blue-600 hover:text-blue-900">
                        📄 دانلود
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
