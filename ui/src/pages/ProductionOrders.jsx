import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui'

export default function ProductionOrders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    customer_name: '',
    invoice_number: '',
    delivery_date: '',
    priority: 'white',
    product_model: '',
    lines: [{ line_number: 1, quantity: 1, wood_color: '', fabric_color: '', fabric_code: '' }]
  })

  useEffect(() => {
    loadOrders()
  }, [])

  const loadOrders = async () => {
    try {
      const response = await fetch('/api/office-forms/production-orders/')
      const data = await response.json()
      if (data.success) {
        setOrders(data.results)
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
      const response = await fetch('/api/office-forms/production-orders/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      const data = await response.json()
      if (data.success) {
        setShowForm(false)
        loadOrders()
      }
    } catch (error) {
      console.error('خطا:', error)
    }
  }

  const addLine = () => {
    setFormData({
      ...formData,
      lines: [...formData.lines, { 
        line_number: formData.lines.length + 1, 
        quantity: 1, 
        wood_color: '', 
        fabric_color: '', 
        fabric_code: '' 
      }]
    })
  }

  const updateLine = (index, field, value) => {
    const newLines = [...formData.lines]
    newLines[index][field] = value
    setFormData({ ...formData, lines: newLines })
  }

  const downloadExcel = (id) => {
    window.location.href = `/api/office-forms/production-orders/${id}/export-excel/`
  }

  const getPriorityColor = (priority) => {
    const colors = {
      red: 'bg-red-100 text-red-800',
      yellow: 'bg-yellow-100 text-yellow-800',
      white: 'bg-gray-100 text-gray-800'
    }
    return colors[priority] || 'bg-gray-100'
  }

  if (loading) return <div className="p-8">در حال بارگذاری...</div>

  return (
    <div className="container mx-auto p-6" dir="rtl">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>سفارشات تولید</CardTitle>
            <button
              onClick={() => setShowForm(!showForm)}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              {showForm ? 'لغو' : '+ سفارش جدید'}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {showForm && (
            <form onSubmit={handleSubmit} className="mb-6 p-4 border rounded-lg bg-gray-50">
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium mb-1">نام مشتری/نمایندگی</label>
                  <input
                    type="text"
                    required
                    value={formData.customer_name}
                    onChange={(e) => setFormData({ ...formData, customer_name: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">شماره فاکتور</label>
                  <input
                    type="text"
                    value={formData.invoice_number}
                    onChange={(e) => setFormData({ ...formData, invoice_number: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">تاریخ تحویل</label>
                  <input
                    type="date"
                    required
                    value={formData.delivery_date}
                    onChange={(e) => setFormData({ ...formData, delivery_date: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">اولویت</label>
                  <select
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    <option value="white">سفید - عادی</option>
                    <option value="yellow">زرد - فوری</option>
                    <option value="red">قرمز - بسیار فوری</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-sm font-medium mb-1">مدل محصول</label>
                  <input
                    type="text"
                    value={formData.product_model}
                    onChange={(e) => setFormData({ ...formData, product_model: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  />
                </div>
              </div>

              <div className="border-t pt-4 mt-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-medium">آیتم‌های سفارش</h3>
                  <button type="button" onClick={addLine} className="text-blue-600 text-sm">
                    + افزودن ردیف
                  </button>
                </div>
                {formData.lines.map((line, index) => (
                  <div key={index} className="grid grid-cols-5 gap-2 mb-2">
                    <input
                      type="number"
                      placeholder="تعداد"
                      value={line.quantity}
                      onChange={(e) => updateLine(index, 'quantity', e.target.value)}
                      className="px-2 py-1 border rounded text-sm"
                    />
                    <input
                      type="text"
                      placeholder="رنگ چوب"
                      value={line.wood_color}
                      onChange={(e) => updateLine(index, 'wood_color', e.target.value)}
                      className="px-2 py-1 border rounded text-sm"
                    />
                    <input
                      type="text"
                      placeholder="رنگ پارچه"
                      value={line.fabric_color}
                      onChange={(e) => updateLine(index, 'fabric_color', e.target.value)}
                      className="px-2 py-1 border rounded text-sm"
                    />
                    <input
                      type="text"
                      placeholder="کد پارچه"
                      value={line.fabric_code}
                      onChange={(e) => updateLine(index, 'fabric_code', e.target.value)}
                      className="px-2 py-1 border rounded text-sm"
                    />
                    <span className="text-sm text-gray-500 self-center">ردیف {index + 1}</span>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex gap-2">
                <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded-md">
                  ثبت سفارش
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
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">مشتری</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">تحویل</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">اولویت</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">وضعیت</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">عملیات</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y">
                {orders.map((order) => (
                  <tr key={order.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">{order.reference_code}</td>
                    <td className="px-4 py-3 text-sm">{order.customer_name}</td>
                    <td className="px-4 py-3 text-sm">{new Date(order.delivery_date).toLocaleDateString('fa-IR')}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${getPriorityColor(order.priority)}`}>
                        {order.priority_label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">{order.status_label}</td>
                    <td className="px-4 py-3 text-sm">
                      <button onClick={() => downloadExcel(order.id)} className="text-blue-600">
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
