import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui'

export default function AttendanceConfirmations() {
  const [confirmations, setConfirmations] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    employee_name: '',
    employee_code: '',
    month_year: '',
    work_days: '',
    overtime_hours: '',
    absence_days: '',
    leave_days: '',
    notes: ''
  })

  useEffect(() => {
    loadConfirmations()
  }, [])

  const loadConfirmations = async () => {
    try {
      const response = await fetch('/api/office-forms/attendance-confirmations/')
      const data = await response.json()
      if (data.success) {
        setConfirmations(data.results)
      }
    } catch (error) {
      console.error('خطا:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const response = await fetch('/api/office-forms/attendance-confirmations/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      const data = await response.json()
      if (data.success) {
        setShowForm(false)
        setFormData({
          employee_name: '',
          employee_code: '',
          month_year: '',
          work_days: '',
          overtime_hours: '',
          absence_days: '',
          leave_days: '',
          notes: ''
        })
        loadConfirmations()
      }
    } catch (error) {
      console.error('خطا:', error)
    }
  }

  const downloadExcel = (id) => {
    window.location.href = `/api/office-forms/attendance-confirmations/${id}/export-excel/`
  }

  const getStatusColor = (status) => {
    const colors = {
      draft: 'bg-gray-100 text-gray-800',
      submitted: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800'
    }
    return colors[status] || 'bg-gray-100'
  }

  if (loading) return <div className="p-8">در حال بارگذاری...</div>

  return (
    <div className="container mx-auto p-6" dir="rtl">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>تایید کارکرد پرسنل</CardTitle>
            <button
              onClick={() => setShowForm(!showForm)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              {showForm ? 'لغو' : '+ ثبت کارکرد جدید'}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {showForm && (
            <form onSubmit={handleSubmit} className="mb-6 p-4 border rounded-lg bg-gray-50">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">نام و نام خانوادگی</label>
                  <input
                    type="text"
                    required
                    value={formData.employee_name}
                    onChange={(e) => setFormData({ ...formData, employee_name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">کد پرسنلی</label>
                  <input
                    type="text"
                    required
                    value={formData.employee_code}
                    onChange={(e) => setFormData({ ...formData, employee_code: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">ماه و سال (مثال: 1403/06)</label>
                  <input
                    type="text"
                    required
                    placeholder="1403/06"
                    value={formData.month_year}
                    onChange={(e) => setFormData({ ...formData, month_year: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">تعداد روز کار</label>
                  <input
                    type="number"
                    required
                    value={formData.work_days}
                    onChange={(e) => setFormData({ ...formData, work_days: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">ساعت اضافه کار</label>
                  <input
                    type="number"
                    step="0.5"
                    value={formData.overtime_hours}
                    onChange={(e) => setFormData({ ...formData, overtime_hours: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">تعداد غیبت</label>
                  <input
                    type="number"
                    value={formData.absence_days}
                    onChange={(e) => setFormData({ ...formData, absence_days: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">تعداد مرخصی</label>
                  <input
                    type="number"
                    value={formData.leave_days}
                    onChange={(e) => setFormData({ ...formData, leave_days: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div className="col-span-2">
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
                <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded-md">
                  ثبت کارکرد
                </button>
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-300 rounded-md">
                  انصراف
                </button>
              </div>
            </form>
          )}

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">کد</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">نام پرسنل</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">کد پرسنلی</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">ماه/سال</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">روز کار</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">وضعیت</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">عملیات</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y">
                {confirmations.map((conf) => (
                  <tr key={conf.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">{conf.reference_code}</td>
                    <td className="px-4 py-3 text-sm">{conf.employee_name}</td>
                    <td className="px-4 py-3 text-sm">{conf.employee_code}</td>
                    <td className="px-4 py-3 text-sm">{conf.month_year}</td>
                    <td className="px-4 py-3 text-sm">{conf.work_days}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(conf.status)}`}>
                        {conf.status_label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <button onClick={() => downloadExcel(conf.id)} className="text-blue-600">
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
