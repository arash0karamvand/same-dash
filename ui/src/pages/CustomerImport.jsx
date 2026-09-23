import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui'

export default function CustomerImport() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0]
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.xlsx')) {
        setError('فقط فایل‌های اکسل (.xlsx) پذیرفته می‌شوند')
        setFile(null)
        return
      }
      setFile(selectedFile)
      setError(null)
    }
  }

  const handleUpload = async () => {
    if (!file) {
      setError('لطفاً یک فایل انتخاب کنید')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('/api/customers/import/', {
        method: 'POST',
        body: formData
      })
      
      const data = await response.json()
      
      if (data.success) {
        setResult(data)
        setFile(null)
        // Reset file input
        document.getElementById('file-input').value = ''
      } else {
        setError(data.message || 'خطا در import فایل')
      }
    } catch (err) {
      setError('خطا در ارتباط با سرور: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  const downloadSample = () => {
    // دانلود فایل نمونه
    window.location.href = '/api/customers/export/?limit=5'
  }

  return (
    <div className="container mx-auto p-6 max-w-4xl" dir="rtl">
      <Card>
        <CardHeader>
          <CardTitle>وارد کردن مشتریان از اکسل</CardTitle>
          <CardDescription>
            آپلود فایل اکسل برای افزودن یا به‌روزرسانی مشتریان به صورت دسته‌ای
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* راهنما */}
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h3 className="font-semibold mb-2 text-blue-900">📋 راهنمای استفاده:</h3>
            <ul className="text-sm text-blue-800 space-y-1 mr-4">
              <li>• فایل باید فرمت اکسل (.xlsx) باشد</li>
              <li>• ستون‌های مورد نیاز: نام، تلفن (الزامی)</li>
              <li>• ستون‌های اختیاری: آدرس، ایمیل، کد عضویت، تولد</li>
              <li>• اگر تلفن تکراری باشد، اطلاعات مشتری به‌روز می‌شود</li>
              <li>• برای مشاهده فرمت صحیح، فایل نمونه دانلود کنید</li>
            </ul>
            <button
              onClick={downloadSample}
              className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
            >
              📥 دانلود فایل نمونه
            </button>
          </div>

          {/* انتخاب فایل */}
          <div className="mb-6">
            <label className="block text-sm font-medium mb-2">
              انتخاب فایل اکسل:
            </label>
            <div className="flex items-center gap-3">
              <input
                id="file-input"
                type="file"
                accept=".xlsx"
                onChange={handleFileChange}
                className="flex-1 px-3 py-2 border rounded-md"
                disabled={loading}
              />
              <button
                onClick={handleUpload}
                disabled={!file || loading}
                className={`px-6 py-2 rounded-md font-medium ${
                  !file || loading
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
              >
                {loading ? 'در حال پردازش...' : 'آپلود و Import'}
              </button>
            </div>
            {file && (
              <p className="mt-2 text-sm text-gray-600">
                فایل انتخاب شده: <span className="font-medium">{file.name}</span> 
                ({(file.size / 1024).toFixed(2)} KB)
              </p>
            )}
          </div>

          {/* خطا */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-800 font-medium">❌ {error}</p>
            </div>
          )}

          {/* نتیجه موفق */}
          {result && (
            <div className="p-6 bg-green-50 border border-green-200 rounded-lg">
              <h3 className="font-semibold text-green-900 mb-4 text-lg">
                ✅ Import با موفقیت انجام شد
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-3 bg-white rounded-md">
                  <div className="text-2xl font-bold text-blue-600">{result.total || 0}</div>
                  <div className="text-sm text-gray-600">کل رکوردها</div>
                </div>
                <div className="text-center p-3 bg-white rounded-md">
                  <div className="text-2xl font-bold text-green-600">{result.created || 0}</div>
                  <div className="text-sm text-gray-600">جدید</div>
                </div>
                <div className="text-center p-3 bg-white rounded-md">
                  <div className="text-2xl font-bold text-orange-600">{result.updated || 0}</div>
                  <div className="text-sm text-gray-600">به‌روز شده</div>
                </div>
                <div className="text-center p-3 bg-white rounded-md">
                  <div className="text-2xl font-bold text-red-600">{result.errors || 0}</div>
                  <div className="text-sm text-gray-600">خطا</div>
                </div>
              </div>

              {result.error_details && result.error_details.length > 0 && (
                <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                  <h4 className="font-medium text-yellow-900 mb-2">⚠️ خطاهای رخ داده:</h4>
                  <ul className="text-sm text-yellow-800 space-y-1">
                    {result.error_details.map((err, idx) => (
                      <li key={idx}>
                        • {err.name} ({err.phone}): {err.error}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-4 text-center">
                <a
                  href="/customers"
                  className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  مشاهده لیست مشتریان
                </a>
              </div>
            </div>
          )}

          {/* Loading Spinner */}
          {loading && (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
              <p className="text-gray-600">در حال پردازش فایل...</p>
              <p className="text-sm text-gray-500 mt-1">لطفاً صبر کنید</p>
            </div>
          )}

          {/* توضیحات */}
          <div className="mt-8 p-4 bg-gray-50 border rounded-lg">
            <h4 className="font-medium mb-2">📌 نکات مهم:</h4>
            <ul className="text-sm text-gray-700 space-y-1 mr-4">
              <li>• حداکثر حجم فایل: 5 مگابایت</li>
              <li>• تلفن باید 11 رقمی و منحصر به فرد باشد</li>
              <li>• در صورت وجود تلفن تکراری، اطلاعات قبلی به‌روز می‌شود</li>
              <li>• فرآیند import ممکن است بسته به تعداد رکوردها چند ثانیه طول بکشد</li>
            </ul>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
