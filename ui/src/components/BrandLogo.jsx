// لوگوی سایت — از تنظیمات خوانده می‌شود و در صورت نبود تصویر، آیکون پیش‌فرض نشان داده می‌شود.

import { useEffect, useState } from 'react'
import Icon from './icons/Icon'
import { useConfig } from '../context/ConfigContext'

export default function BrandLogo({ size = 32, className = '', alt = 'لوگوی شرکت' }) {
  const { logoUrl } = useConfig()
  const [failed, setFailed] = useState(false)

  useEffect(() => { setFailed(false) }, [logoUrl])

  const classes = `brand-logo${className ? ` ${className}` : ''}`

  if (!logoUrl || failed) {
    return (
      <span className={classes} style={{ width: size, height: size }}>
        <Icon name="diamond" size={Math.round(size * 0.7)} />
      </span>
    )
  }

  return (
    <span className={classes} style={{ width: size, height: size }}>
      <img src={logoUrl} alt={alt} className="brand-logo-img" onError={() => setFailed(true)} />
    </span>
  )
}
