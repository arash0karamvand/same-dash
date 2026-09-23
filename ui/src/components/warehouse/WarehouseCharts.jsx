import { useMemo } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Bar, Line, Pie, Doughnut } from 'react-chartjs-2'
import { fromLegacy } from '../../styles/tw.js'

// ثبت کامپوننت‌های Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const CHART_COLORS = {
  primary: '#3b82f6',
  success: '#22c55e',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#06b6d4',
  purple: '#8b5cf6',
  pink: '#ec4899',
  gray: '#6b7280',
}

const DEFAULT_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top',
      rtl: true,
      labels: {
        font: {
          family: 'Vazirmatn, sans-serif',
          size: 12,
        },
        usePointStyle: true,
        padding: 15,
      },
    },
    tooltip: {
      rtl: true,
      bodyFont: {
        family: 'Vazirmatn, sans-serif',
      },
      titleFont: {
        family: 'Vazirmatn, sans-serif',
      },
    },
  },
}

/**
 * نمودار میله‌ای موجودی به تفکیک نوع مصرف
 */
export function InventoryByUsageChart({ data }) {
  const chartData = useMemo(() => {
    if (!data || !Array.isArray(data)) return null
    
    return {
      labels: data.map((item) => item.usage_kind_display),
      datasets: [
        {
          label: 'ارزش موجودی (ریال)',
          data: data.map((item) => item.inventory_value),
          backgroundColor: [
            CHART_COLORS.primary,
            CHART_COLORS.success,
            CHART_COLORS.warning,
            CHART_COLORS.danger,
            CHART_COLORS.info,
            CHART_COLORS.purple,
            CHART_COLORS.pink,
          ],
          borderWidth: 0,
          borderRadius: 8,
        },
      ],
    }
  }, [data])

  if (!chartData) return null

  return (
    <div style={{ height: '300px' }}>
      <Bar
        data={chartData}
        options={{
          ...DEFAULT_OPTIONS,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                },
                callback: (value) => value.toLocaleString('fa-IR'),
              },
            },
            x: {
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                },
              },
            },
          },
        }}
      />
    </div>
  )
}

/**
 * نمودار دایره‌ای ABC
 */
export function AbcClassificationChart({ counts, values }) {
  const chartData = useMemo(() => {
    if (!counts || !values) return null
    
    return {
      labels: ['دسته A (۸۰٪)', 'دسته B (۱۵٪)', 'دسته C (۵٪)'],
      datasets: [
        {
          label: 'تعداد قلم',
          data: [counts.A || 0, counts.B || 0, counts.C || 0],
          backgroundColor: [
            CHART_COLORS.danger,
            CHART_COLORS.warning,
            CHART_COLORS.success,
          ],
          borderWidth: 2,
          borderColor: '#fff',
        },
      ],
    }
  }, [counts, values])

  if (!chartData) return null

  return (
    <div style={{ height: '300px' }}>
      <Doughnut
        data={chartData}
        options={{
          ...DEFAULT_OPTIONS,
          plugins: {
            ...DEFAULT_OPTIONS.plugins,
            legend: {
              ...DEFAULT_OPTIONS.plugins.legend,
              position: 'bottom',
            },
          },
        }}
      />
    </div>
  )
}

/**
 * نمودار خطی مصرف در بازه زمانی
 */
export function ConsumptionTrendChart({ data }) {
  const chartData = useMemo(() => {
    if (!data || !Array.isArray(data) || data.length === 0) return null
    
    // گرفتن top 10 متریال
    const topMaterials = data.slice(0, 10)
    
    return {
      labels: topMaterials.map((item) => item.label),
      datasets: [
        {
          label: 'مصرف',
          data: topMaterials.map((item) => item.consumed_quantity),
          borderColor: CHART_COLORS.danger,
          backgroundColor: `${CHART_COLORS.danger}33`,
          borderWidth: 2,
          fill: true,
          tension: 0.4,
        },
        {
          label: 'برگشت',
          data: topMaterials.map((item) => item.returned_quantity),
          borderColor: CHART_COLORS.success,
          backgroundColor: `${CHART_COLORS.success}33`,
          borderWidth: 2,
          fill: true,
          tension: 0.4,
        },
      ],
    }
  }, [data])

  if (!chartData) return null

  return (
    <div style={{ height: '350px' }}>
      <Bar
        data={chartData}
        options={{
          ...DEFAULT_OPTIONS,
          indexAxis: 'y',
          scales: {
            x: {
              beginAtZero: true,
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                },
              },
            },
            y: {
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                  size: 10,
                },
              },
            },
          },
        }}
      />
    </div>
  )
}

/**
 * نمودار پوشش روز
 */
export function CoverageDaysChart({ data }) {
  const chartData = useMemo(() => {
    if (!data || !Array.isArray(data)) return null
    
    // مرتب‌سازی بر اساس روزهای پوشش و گرفتن موارد کمتر از 30 روز
    const sorted = [...data]
      .filter((item) => item.days_of_cover < 30)
      .sort((a, b) => a.days_of_cover - b.days_of_cover)
      .slice(0, 15)
    
    if (sorted.length === 0) return null
    
    return {
      labels: sorted.map((item) => item.label),
      datasets: [
        {
          label: 'روز پوشش',
          data: sorted.map((item) => item.days_of_cover),
          backgroundColor: sorted.map((item) => {
            if (item.days_of_cover < 7) return CHART_COLORS.danger
            if (item.days_of_cover < 15) return CHART_COLORS.warning
            return CHART_COLORS.success
          }),
          borderRadius: 8,
        },
      ],
    }
  }, [data])

  if (!chartData) return null

  return (
    <div style={{ height: '400px' }}>
      <Bar
        data={chartData}
        options={{
          ...DEFAULT_OPTIONS,
          indexAxis: 'y',
          scales: {
            x: {
              beginAtZero: true,
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                },
              },
            },
            y: {
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                  size: 10,
                },
              },
            },
          },
          plugins: {
            ...DEFAULT_OPTIONS.plugins,
            tooltip: {
              ...DEFAULT_OPTIONS.plugins.tooltip,
              callbacks: {
                label: (context) => {
                  const value = context.parsed.x
                  if (value < 7) return `${value} روز (بحرانی)`
                  if (value < 15) return `${value} روز (هشدار)`
                  return `${value} روز (خوب)`
                },
              },
            },
          },
        }}
      />
    </div>
  )
}

/**
 * نمودار کسری صف ساخت
 */
export function ShortageChart({ data }) {
  const chartData = useMemo(() => {
    if (!data || !Array.isArray(data)) return null
    
    // top 10 کسری به ترتیب ارزش
    const topShortage = data.slice(0, 10)
    
    return {
      labels: topShortage.map((item) => item.label),
      datasets: [
        {
          label: 'ارزش خرید پیشنهادی (ریال)',
          data: topShortage.map((item) => item.suggested_value),
          backgroundColor: CHART_COLORS.danger,
          borderRadius: 8,
        },
      ],
    }
  }, [data])

  if (!chartData) return null

  return (
    <div style={{ height: '350px' }}>
      <Bar
        data={chartData}
        options={{
          ...DEFAULT_OPTIONS,
          indexAxis: 'y',
          scales: {
            x: {
              beginAtZero: true,
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                },
                callback: (value) => value.toLocaleString('fa-IR'),
              },
            },
            y: {
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                  size: 10,
                },
              },
            },
          },
        }}
      />
    </div>
  )
}

/**
 * نمودار موجودی راکد
 */
export function IdleInventoryChart({ data }) {
  const chartData = useMemo(() => {
    if (!data || !Array.isArray(data)) return null
    
    // top 10 موجودی راکد به ترتیب ارزش
    const topIdle = data.slice(0, 10)
    
    return {
      labels: topIdle.map((item) => item.label),
      datasets: [
        {
          label: 'ارزش موجودی راکد (ریال)',
          data: topIdle.map((item) => item.inventory_value),
          backgroundColor: CHART_COLORS.warning,
          borderRadius: 8,
        },
      ],
    }
  }, [data])

  if (!chartData) return null

  return (
    <div style={{ height: '350px' }}>
      <Bar
        data={chartData}
        options={{
          ...DEFAULT_OPTIONS,
          indexAxis: 'y',
          scales: {
            x: {
              beginAtZero: true,
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                },
                callback: (value) => value.toLocaleString('fa-IR'),
              },
            },
            y: {
              ticks: {
                font: {
                  family: 'Vazirmatn, sans-serif',
                  size: 10,
                },
              },
            },
          },
        }}
      />
    </div>
  )
}
