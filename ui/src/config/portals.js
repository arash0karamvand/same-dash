// چهار پورتال — مدیران / فروشگاه / اداری / کارخانه

export const PORTALS = [
  {
    id: 'managers',
    label: 'مدیران',
    icon: '👔',
    executiveOnly: true,
    defaultPage: 'dashboard',
    children: [
      { key: 'dashboard', label: 'داشبورد', icon: '📊', permission: 'view_dashboard' },
      { key: 'orders', label: 'صف ارسال به اداری', icon: '📋', executiveOnly: true },
      { key: 'users', label: 'کاربران', icon: '🛡️', systemAdmin: true },
      { key: 'roles', label: 'نقش‌ها و دسترسی', icon: '🔐', systemAdmin: true },
      { key: 'settings', label: 'تنظیمات سیستم', icon: '⚙️', systemAdmin: true },
      { key: 'orgchart', label: 'چارت سازمانی', icon: '🏢', permission: 'view_org_chart' },
      { key: 'managers', label: 'مدیران پرسنل', icon: '👥', anyPermission: ['view_managers', 'manage_managers'] },
      { key: 'sellers', label: 'فروشندگان', icon: '🧑‍💼', anyPermission: ['view_sellers', 'manage_staff'] },
      { key: 'ranking', label: 'رده‌بندی کارکنان', icon: '🏆', permission: 'view_employee_ranking' },
      { key: 'attendance', label: 'حضور و غیاب', icon: '📅', permission: 'view_attendance' },
      { key: 'levels', label: 'باشگاه و سطوح', icon: '🏅', permission: 'view_loyalty' },
      { key: 'sms', label: 'پیامک', icon: '✉️', anyPermission: ['send_sms', 'view_sms_logs'] },
      { key: 'logs', label: 'لاگ‌ها', icon: '📜', permission: 'view_audit_logs' },
    ],
  },
  {
    id: 'shop',
    label: 'فروشگاه',
    icon: '🏪',
    defaultPage: 'shop',
    children: [
      { key: 'shop', label: 'سفارش‌ها', icon: '🧾', anyPermission: ['create_sale', 'approve_sale_branch', 'view_sales_summary', 'view_sales'] },
      { key: 'customers', label: 'مشتریان', icon: '👥', permission: 'view_customers' },
      { key: 'products', label: 'محصولات', icon: '📦', permission: 'view_products' },
    ],
  },
  {
    id: 'office',
    label: 'اداری',
    icon: '🏢',
    defaultPage: 'office',
    children: [
      { key: 'office', label: 'تایید سفارش', icon: '📋', permission: 'approve_sale_accounting' },
      { key: 'customers', label: 'مشتریان', icon: '👥', permission: 'view_customers' },
      { key: 'accounting', label: 'حسابداری', icon: '💰', permission: 'view_accounting' },
      { key: 'checks', label: 'چک و اقساط', icon: '📋', permission: 'view_installments' },
      { key: 'factory', label: 'کارخانه — ساخت', icon: '🔧', permission: 'view_factory_orders' },
      { key: 'factory-built', label: 'کارخانه — ساخته‌شده', icon: '✅', permission: 'view_factory_orders' },
      { key: 'freight', label: 'کارخانه — باربری', icon: '🚚', permission: 'view_freight_orders' },
    ],
  },
  {
    id: 'factory',
    label: 'کارخانه',
    icon: '🏭',
    defaultPage: 'factory',
    children: [
      { key: 'factory', label: 'ساخت', icon: '🔧', permission: 'view_factory_orders' },
      { key: 'factory-built', label: 'ساخته‌شده‌ها', icon: '✅', permission: 'view_factory_orders' },
      { key: 'freight', label: 'باربری', icon: '🚚', anyPermission: ['view_freight_orders', 'manage_freight_orders'] },
    ],
  },
]

export function getPortal(id) {
  return PORTALS.find((p) => p.id === id)
}

export function getPortalChild(portalId, pageKey) {
  const portal = getPortal(portalId)
  return portal?.children?.find((c) => c.key === pageKey)
}
