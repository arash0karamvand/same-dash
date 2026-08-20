// لوگوی سایت — کش محلی تا صفحه ورود (قبل از احراز هویت) و فاکتور چاپی هم به آن دسترسی داشته باشند.

export const DEFAULT_LOGO_URL = '/company_logo.png'

const STORAGE_KEY = 'site-logo'

let currentLogo = DEFAULT_LOGO_URL

try {
  const cached = localStorage.getItem(STORAGE_KEY)
  if (cached) currentLogo = cached
} catch {
  // دسترسی به localStorage ممکن است مسدود باشد — از پیش‌فرض استفاده می‌کنیم.
}

export function getLogoUrl() {
  return currentLogo || DEFAULT_LOGO_URL
}

export function setLogoUrl(url) {
  currentLogo = url || DEFAULT_LOGO_URL
  try {
    if (currentLogo === DEFAULT_LOGO_URL) localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, currentLogo)
  } catch {
    // نادیده — کش اختیاری است.
  }
  return currentLogo
}

/** فایل انتخابی کاربر را به data URL با حداکثر عرض/ارتفاع مشخص تبدیل می‌کند. */
export function fileToLogoDataUrl(file, maxSize = 512) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject(new Error('فایلی انتخاب نشده است.'))
      return
    }
    if (!file.type.startsWith('image/')) {
      reject(new Error('فقط فایل تصویری قابل انتخاب است.'))
      return
    }

    const reader = new FileReader()
    reader.onerror = () => reject(new Error('خواندن فایل ناموفق بود.'))
    reader.onload = () => {
      const dataUrl = String(reader.result || '')
      // SVG برداری است و نیازی به تغییر اندازه ندارد.
      if (file.type === 'image/svg+xml') {
        resolve(dataUrl)
        return
      }

      const img = new Image()
      img.onerror = () => reject(new Error('تصویر قابل خواندن نیست.'))
      img.onload = () => {
        const scale = Math.min(1, maxSize / Math.max(img.width, img.height))
        const width = Math.max(1, Math.round(img.width * scale))
        const height = Math.max(1, Math.round(img.height * scale))
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')
        ctx.drawImage(img, 0, 0, width, height)
        // PNG تا شفافیت لوگو حفظ شود.
        resolve(canvas.toDataURL('image/png'))
      }
      img.src = dataUrl
    }
    reader.readAsDataURL(file)
  })
}
