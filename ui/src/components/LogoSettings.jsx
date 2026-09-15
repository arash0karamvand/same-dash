// مدیریت لوگوی سایت — آپلود، پیش‌نمایش و بازگشت به لوگوی پیش‌فرض.

import { useRef, useState } from 'react'
import { configApi } from '../api/client'
import { Button } from './ui'
import { useConfig } from '../context/ConfigContext'
import { fileToLogoDataUrl } from '../utils/branding'
import { fromLegacy } from '../styles/tw.js'

export default function LogoSettings({ onError, onInfo }) {
  const { logoUrl, branding, applyBranding } = useConfig()
  const inputRef = useRef(null)
  const [busy, setBusy] = useState(false)

  const pickFile = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    setBusy(true)
    try {
      const dataUrl = await fileToLogoDataUrl(file)
      const saved = await configApi.saveLogo(dataUrl, file.name)
      applyBranding(saved)
      onInfo?.('لوگوی سایت به‌روز شد.')
      onError?.('')
    } catch (err) {
      onError?.(err.message)
    } finally {
      setBusy(false)
    }
  }

  const reset = async () => {
    setBusy(true)
    try {
      const saved = await configApi.resetLogo()
      applyBranding(saved)
      onInfo?.('لوگو به حالت پیش‌فرض برگشت.')
      onError?.('')
    } catch (err) {
      onError?.(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={fromLegacy("logo-settings")}>
      <div className={fromLegacy("logo-settings-preview")}>
        <img src={logoUrl} alt="لوگوی فعلی سایت" />
      </div>

      <div className={fromLegacy("logo-settings-body")}>
        <h4>لوگوی سایت</h4>
        <p className={fromLegacy("muted")}>
          این لوگو در سایدبار، صفحه ورود و فاکتور چاپی نمایش داده می‌شود. تصویر با پس‌زمینه شفاف
          (PNG یا SVG) بهترین نتیجه را می‌دهد و به‌صورت خودکار تا ۵۱۲ پیکسل کوچک می‌شود.
        </p>

        <div className={fromLegacy("logo-settings-meta")}>
          <span>وضعیت: {branding?.logo_is_custom ? 'لوگوی سفارشی' : 'لوگوی پیش‌فرض پروژه'}</span>
          {branding?.logo_name && <span>فایل: {branding.logo_name}</span>}
        </div>

        <div className={fromLegacy("logo-settings-actions")}>
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/svg+xml"
            onChange={pickFile}
            hidden
          />
          <Button type="button" onClick={() => inputRef.current?.click()} disabled={busy}>
            {busy ? 'در حال ذخیره…' : 'انتخاب لوگوی جدید'}
          </Button>
          {branding?.logo_is_custom && (
            <Button type="button" variant="ghost" onClick={reset} disabled={busy}>
              بازگشت به پیش‌فرض
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
