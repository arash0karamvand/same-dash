import { useMemo } from 'react'
import { Card, StatCard, EmptyState } from '../ui'
import { formatMoney, formatNumber } from '../../utils/format'
import { fromLegacy } from '../../styles/tw.js'
import {
  InventoryByUsageChart,
  AbcClassificationChart,
  ShortageChart,
  CoverageDaysChart,
  IdleInventoryChart,
} from './WarehouseCharts'

/**
 * Dashboard خلاصه گزارش انبار
 */
export function WarehouseDashboard({ summaryData, shortageData, coverageData, idleData, abcData, onNavigate }) {
  // محاسبه KPIهای کلیدی
  const kpis = useMemo(() => {
    if (!summaryData) return null

    const totalValue = summaryData.inventory_value || 0
    const itemCount = summaryData.item_count || 0
    const zeroCount = summaryData.zero_count || 0
    const shortageCount = summaryData.shortage_count || 0
    const shortageValue = summaryData.shortage_value || 0
    const consumptionValue = summaryData.consumption_value || 0

    // درصد بدون موجودی
    const zeroPercent = itemCount > 0 ? ((zeroCount / itemCount) * 100).toFixed(1) : 0

    // درصد کسری
    const shortagePercent = itemCount > 0 ? ((shortageCount / itemCount) * 100).toFixed(1) : 0

    return {
      totalValue,
      itemCount,
      zeroCount,
      zeroPercent,
      shortageCount,
      shortagePercent,
      shortageValue,
      consumptionValue,
    }
  }, [summaryData])

  if (!kpis) {
    return (
      <div className={fromLegacy('loading')} style={{ padding: '40px' }}>
        در حال بارگذاری داشبورد...
      </div>
    )
  }

  return (
    <div style={{ paddingBottom: '20px' }}>
      {/* هدر Dashboard */}
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '8px' }}>
          📊 داشبورد انبار
        </h2>
        <p className={fromLegacy('muted')}>
          نمای کلی وضعیت انبار، موجودی، کسری و هشدارها
        </p>
      </div>

      {/* KPI Cards - خط اول */}
      <div className={fromLegacy('stat-grid')} style={{ marginBottom: '24px' }}>
        <StatCard
          label="ارزش کل موجودی"
          value={formatMoney(kpis.totalValue)}
          trend="up"
          accent="var(--primary)"
        />
        <StatCard
          label="تعداد قلم"
          value={formatNumber(kpis.itemCount)}
          hint="قلم فعال"
          accent="var(--info)"
        />
        <StatCard
          label="بدون موجودی"
          value={`${formatNumber(kpis.zeroCount)} (${kpis.zeroPercent}٪)`}
          accent="var(--warning)"
          onClick={() => onNavigate && onNavigate('stock')}
        />
        <StatCard
          label="کسری صف ساخت"
          value={`${formatNumber(kpis.shortageCount)} (${kpis.shortagePercent}٪)`}
          hint={formatMoney(kpis.shortageValue)}
          accent="var(--danger)"
          onClick={() => onNavigate && onNavigate('shortage')}
        />
      </div>

      {/* KPI Cards - خط دوم */}
      <div className={fromLegacy('stat-grid')} style={{ marginBottom: '32px', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        <StatCard
          label="ارزش مصرف ۳۰ روز"
          value={formatMoney(kpis.consumptionValue)}
          accent="var(--purple)"
          onClick={() => onNavigate && onNavigate('consumption')}
        />
        {abcData?.counts && (
          <>
            <StatCard
              label="دسته A (۸۰٪)"
              value={formatNumber(abcData.counts.A || 0)}
              hint={formatMoney(abcData.values.A || 0)}
              accent="var(--danger)"
              onClick={() => onNavigate && onNavigate('abc')}
            />
            <StatCard
              label="دسته B (۱۵٪)"
              value={formatNumber(abcData.counts.B || 0)}
              hint={formatMoney(abcData.values.B || 0)}
              accent="var(--warning)"
              onClick={() => onNavigate && onNavigate('abc')}
            />
            <StatCard
              label="دسته C (۵٪)"
              value={formatNumber(abcData.counts.C || 0)}
              hint={formatMoney(abcData.values.C || 0)}
              accent="var(--success)"
              onClick={() => onNavigate && onNavigate('abc')}
            />
          </>
        )}
      </div>

      {/* نمودارها - Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px', marginBottom: '24px' }}>
        {/* نمودار موجودی به تفکیک نوع */}
        {summaryData?.by_usage_kind && summaryData.by_usage_kind.length > 0 && (
          <Card title="موجودی به تفکیک نوع مصرف">
            <InventoryByUsageChart data={summaryData.by_usage_kind} />
          </Card>
        )}

        {/* نمودار ABC */}
        {abcData?.counts && (
          <Card title="طبقه‌بندی ABC">
            <AbcClassificationChart counts={abcData.counts} values={abcData.values} />
          </Card>
        )}
      </div>

      {/* نمودارهای بیشتر */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        {/* نمودار کسری صف */}
        {shortageData?.purchase && shortageData.purchase.length > 0 && (
          <Card
            title="🚨 کسری صف ساخت - پیشنهاد خرید"
            action={
              <button
                type="button"
                className={fromLegacy('link')}
                onClick={() => onNavigate && onNavigate('shortage')}
              >
                مشاهده جزئیات ←
              </button>
            }
          >
            <ShortageChart data={shortageData.purchase} />
          </Card>
        )}

        {/* نمودار پوشش روز */}
        {coverageData?.rows && coverageData.rows.length > 0 && (
          <Card
            title="⏱️ پوشش موجودی (کمتر از ۳۰ روز)"
            action={
              <button
                type="button"
                className={fromLegacy('link')}
                onClick={() => onNavigate && onNavigate('coverage')}
              >
                مشاهده همه ←
              </button>
            }
          >
            <CoverageDaysChart data={coverageData.rows} />
          </Card>
        )}

        {/* نمودار موجودی راکد */}
        {idleData?.idle && idleData.idle.length > 0 && (
          <Card
            title="💤 موجودی راکد (بیشترین ارزش)"
            action={
              <button
                type="button"
                className={fromLegacy('link')}
                onClick={() => onNavigate && onNavigate('idle')}
              >
                مشاهده همه ←
              </button>
            }
          >
            <IdleInventoryChart data={idleData.idle} />
          </Card>
        )}
      </div>

      {/* هشدارها و اقدامات پیشنهادی */}
      {(kpis.shortageCount > 0 || kpis.zeroCount > 0) && (
        <Card title="⚠️ هشدارها و اقدامات پیشنهادی" style={{ marginTop: '24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {kpis.shortageCount > 0 && (
              <div
                style={{
                  padding: '12px',
                  background: 'var(--danger-bg)',
                  border: '1px solid var(--danger)',
                  borderRadius: '8px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <strong>کسری صف ساخت</strong>
                  <div className={fromLegacy('muted small')}>
                    {formatNumber(kpis.shortageCount)} قلم نیاز به خرید دارد (ارزش: {formatMoney(kpis.shortageValue)})
                  </div>
                </div>
                <button
                  type="button"
                  className={fromLegacy('link')}
                  onClick={() => onNavigate && onNavigate('shortage')}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  لیست خرید ←
                </button>
              </div>
            )}

            {kpis.zeroCount > 0 && (
              <div
                style={{
                  padding: '12px',
                  background: 'var(--warning-bg)',
                  border: '1px solid var(--warning)',
                  borderRadius: '8px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div>
                  <strong>بدون موجودی</strong>
                  <div className={fromLegacy('muted small')}>
                    {formatNumber(kpis.zeroCount)} قلم موجودی ندارد
                  </div>
                </div>
                <button
                  type="button"
                  className={fromLegacy('link')}
                  onClick={() => onNavigate && onNavigate('stock')}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  مشاهده ←
                </button>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}
