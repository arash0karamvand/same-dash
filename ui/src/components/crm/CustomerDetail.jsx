// کامپوننت جزئیات مشتری برای SlideOver

import { useState } from 'react'
import { Badge, Button, FormSection, StatCard } from '../ui'
import { formatDate, formatMoney, formatNumber } from '../../utils/format'
import { cn, tw } from '../../styles/tw'
import Icon from '../icons/Icon'

export default function CustomerDetail({ customer }) {
  const [tab, setTab] = useState('profile')

  return (
    <div className="space-y-5">
      {/* Tabs */}
      <div className="flex gap-2 border-b border-border-subtle">
        {[
          { id: 'profile', label: 'پروفایل' },
          { id: 'purchases', label: 'خریدها' },
          { id: 'wallet', label: 'کیف پول' },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'px-4 py-2 text-sm font-medium transition-colors',
              tab === t.id
                ? 'border-b-2 border-accent text-text'
                : 'text-muted hover:text-text'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'profile' && (
        <div className="space-y-4">
          <FormSection title="اطلاعات پایه">
            <div className="grid grid-cols-2 gap-3 text-sm max-md:grid-cols-1">
              <div>
                <strong className="text-muted">نام:</strong>
                <div className="mt-1">{customer.name}</div>
              </div>
              <div>
                <strong className="text-muted">موبایل:</strong>
                <div className="mt-1 ltr">{customer.phone}</div>
              </div>
              {customer.level_name && (
                <div>
                  <strong className="text-muted">سطح RFM:</strong>
                  <div className="mt-1">
                    <Badge color={customer.level_color}>{customer.level_name}</Badge>
                  </div>
                </div>
              )}
              {customer.rfm_score !== undefined && (
                <div>
                  <strong className="text-muted">امتیاز:</strong>
                  <div className="mt-1">{formatNumber(customer.rfm_score)}</div>
                </div>
              )}
            </div>
          </FormSection>

          <FormSection title="آمار خرید">
            <div className="grid grid-cols-3 gap-3 max-md:grid-cols-1">
              <StatCard
                label="تعداد خرید"
                value={formatNumber(customer.purchase_count || 0)}
                size="small"
              />
              <StatCard
                label="مجموع خرید"
                value={formatMoney(customer.total_spent || 0)}
                size="small"
              />
              <StatCard
                label="آخرین خرید"
                value={
                  customer.last_purchase_date
                    ? formatDate(customer.last_purchase_date)
                    : '—'
                }
                size="small"
              />
            </div>
          </FormSection>
        </div>
      )}

      {tab === 'purchases' && (
        <div>
          <p className="text-sm text-muted">
            تاریخچه خریدهای مشتری در اینجا نمایش داده می‌شود.
          </p>
        </div>
      )}

      {tab === 'wallet' && (
        <div>
          <div className="rounded-pill border border-jelly-rim bg-layer-1 p-6 text-center">
            <div className="mb-2 text-sm text-muted">موجودی کیف پول</div>
            <div className="mb-4 font-display text-3xl font-bold">
              {formatMoney(customer.wallet_balance || 0)}
            </div>
            <Button size="sm">تنظیم موجودی</Button>
          </div>
        </div>
      )}
    </div>
  )
}
