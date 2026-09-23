import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui'

export default function WarehouseTransfers() {
  const [transfers, setTransfers] = useState([])
  const [warehouses, setWarehouses] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState({
    from_warehouse: '',
    to_warehouse: '',
    notes: '',
    lines: [{ line_number: 1, material_name: '', quantity: '', unit: '' }]
  })

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [transfersRes, warehousesRes] = await Promise.all([
        fetch('/api/office-forms/warehouse-transfers/'),
        fetch('/api/warehouses/')
      ])
      const transfersData = await transfersRes.json()
      const warehousesData = await warehousesRes.json()
      
      if (transfersData.success) setTransfers(transfersData.results)
      if (warehousesData.success) setWarehouses(warehousesData.results)
    } catch (error) {
      console.error('خطا:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const response = await fetch('/api/office-forms/warehouse-transfers/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      })
      const data = await response.json()
      if (data.success) {
        setShowForm(false)
        setFormData({
          from_warehouse: '',
          to_warehouse: '',
          notes: '',
          lines: [{ line_number: 1, material_name: '', quantity: '', unit: '' }]
        })
        loadData()
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
        material_name: '', 
        quantity: '', 
        unit: '' 
      }]
    })
  }

  const updateLine = (index, field, value) => {
    const newLines = [...formData.lines]
    newLines[index][field] = value
    setFormData({ ...formData, lines: newLines })
  }

  const downloadExcel = (id) => {
    window.location.href = `/api/office-forms/warehouse-transfers/${id}/export-excel/`
  }

  const getStatusColor = (status) => {
    const colors = {
      draft: 'bg-gray-100 text-gray-800',
      requested: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800'
    }
    return colors[status] || 'bg-gray-100'
  }

  if (loading) return <div className="p-8">در حال بارگذاری...</div>

  return (
    <div className="container mx-auto p-6" dir="rtl">
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>درخواست‌های جابجایی انبار</CardTitle>
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
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium mb-1">از انبار</label>
                  <select
                    required
                    value={formData.from_warehouse}
                    onChange={(e) => setFormData({ ...formData, from_warehouse: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    <option value="">انتخاب کنید</option>
                    {warehouses.map(w => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">به انبار</label>
                  <select
                    required
                    value={formData.to_warehouse}
                    onChange={(e) => setFormData({ ...formData, to_warehouse: e.target.value })}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    <option value="">انتخاب کنید</option>
                    {warehouses.map(w => (
                      <option key={w.id} value={w.id}>{w.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium mb-1">توضیحات</label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  className="w-full px-3 py-2 border rounded-md"
                  rows="2"
                />
              </div>

              <div className="border-t pt-4 mt-4">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-medium">اقلام</h3>
                  <button type="button" onClick={addLine} className="text-blue-600 text-sm">
                    + افزودن ردیف
                  </button>
                </div>
                {formData.lines.map((line, index) => (
                  <div key={index} className="grid grid-cols-4 gap-2 mb-2">
                    <input
                      type="text"
                      placeholder="نام کالا/مواد"
                      required
                      value={line.material_name}
                      onChange={(e) => updateLine(index, 'material_name', e.target.value)}
                      className="col-span-2 px-2 py-1 border rounded text-sm"
                    />
                    <input
                      type="number"
                      placeholder="مقدار"
                      required
                      value={line.quantity}
                      onChange={(e) => updateLine(index, 'quantity', e.target.value)}
                      className="px-2 py-1 border rounded text-sm"
                    />
                    <input
                      type="text"
                      placeholder="واحد"
                      required
                      value={line.unit}
                      onChange={(e) => updateLine(index, 'unit', e.target.value)}
                      className="px-2 py-1 border rounded text-sm"
                    />
                  </div>
                ))}
              </div>

              <div className="mt-4 flex gap-2">
                <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded-md">
                  ثبت درخواست
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
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">از</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">به</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">تاریخ</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">وضعیت</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">عملیات</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y">
                {transfers.map((transfer) => (
                  <tr key={transfer.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">{transfer.reference_code}</td>
                    <td className="px-4 py-3 text-sm">{transfer.from_warehouse_name}</td>
                    <td className="px-4 py-3 text-sm">{transfer.to_warehouse_name}</td>
                    <td className="px-4 py-3 text-sm">
                      {new Date(transfer.request_date).toLocaleDateString('fa-IR')}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(transfer.status)}`}>
                        {transfer.status_label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <button onClick={() => downloadExcel(transfer.id)} className="text-blue-600">
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
