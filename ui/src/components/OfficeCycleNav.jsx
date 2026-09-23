// نوار مرحله چرخه ارسال در پورتال اداری — هر دکمه همان صفحه موجود را باز می‌کند.

import { resolvePage, routeToPath } from '../utils/routing'
import { fromLegacy } from '../styles/tw.js'

export const OFFICE_CYCLE_STEPS = [
  { page: 'office', label: 'تایید' },
  { page: 'office-orders', label: 'سفارش‌ها' },
  { page: 'factory', label: 'ساخت' },
  { page: 'factory-built', label: 'ساخته‌شده' },
  { page: 'freight', label: 'باربری' },
  { page: 'warehouse', label: 'انبار' },
]

function openOfficePage(page) {
  const path = routeToPath('office', page)
  const resolved = resolvePage('office', page)
  window.history.pushState({ portal: 'office', page: resolved }, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export default function OfficeCycleNav({ current }) {
  return (
    <nav className="mb-3" aria-label="چرخه ارسال">
      <p className={fromLegacy('muted small')}>چرخه ارسال</p>
      <div className={fromLegacy('branch-tabs settings-tabs')}>
        {OFFICE_CYCLE_STEPS.map((step) => (
          <button
            key={step.page}
            type="button"
            className={fromLegacy(`branch-tab ${current === step.page ? 'active' : ''}`)}
            onClick={() => {
              if (step.page !== current) openOfficePage(step.page)
            }}
          >
            {step.label}
          </button>
        ))}
      </div>
    </nav>
  )
}
