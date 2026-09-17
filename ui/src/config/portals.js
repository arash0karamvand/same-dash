// چهار پورتال — مدیران / فروشگاه / اداری / کارخانه

export const PORTALS = [
  {
    id: 'managers',
    label: 'مدیران',
    icon: 'briefcase',
    defaultPage: 'dashboard',
    children: [
      { key: 'dashboard', label: 'داشبورد', icon: 'chart', permission: 'view_dashboard', executiveOnly: true },
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'orders', label: 'صف ارسال به اداری', icon: 'clipboard', executiveOnly: true },
      { key: 'users', label: 'کاربران', icon: 'shield', systemAdmin: true },
      { key: 'roles', label: 'نقش‌ها و دسترسی', icon: 'lock', systemAdmin: true },
      { key: 'settings', label: 'تنظیمات سیستم', icon: 'gear', systemAdmin: true },
      { key: 'cycle', label: 'چرخه', icon: 'clipboard', systemAdmin: true },
      { key: 'cycle-watch', label: 'نظارت چرخه', icon: 'eye', cycleWatch: true },
      { key: 'orgchart', label: 'چارت سازمانی', icon: 'building', permission: 'view_org_chart' },
      { key: 'managers', label: 'مدیران پرسنل', icon: 'users', anyPermission: ['view_managers', 'manage_managers'] },
      { key: 'sellers', label: 'فروشندگان', icon: 'user', anyPermission: ['view_sellers', 'manage_staff'] },
      { key: 'ranking', label: 'رده‌بندی کارکنان', icon: 'trophy', permission: 'view_employee_ranking' },
      { key: 'attendance', label: 'حضور و غیاب', icon: 'calendar', permission: 'view_attendance' },
      { key: 'levels', label: 'باشگاه و سطوح', icon: 'medal', permission: 'view_loyalty' },
      { key: 'sms', label: 'پیامک', icon: 'envelope', anyPermission: ['send_sms', 'view_sms_logs'] },
      { key: 'logs', label: 'لاگ‌ها', icon: 'scroll', permission: 'view_audit_logs' },
      { key: 'filter', label: 'فیلتر', icon: 'search', anyPermission: ['view_dashboard', 'view_audit_logs'] },
    ],
  },
  {
    id: 'shop',
    label: 'فروشگاه',
    icon: 'store',
    defaultPage: 'shop',
    children: [
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'shop', label: 'سفارش‌ها', icon: 'receipt', anyPermission: ['create_sale', 'approve_sale_branch', 'view_sales_summary', 'view_sales'] },
      { key: 'customers', label: 'مشتریان', icon: 'users', permission: 'view_customers' },
      { key: 'products', label: 'محصولات', icon: 'package', permission: 'view_products' },
      { key: 'pickup', label: 'تحویل حضوری', icon: 'store', anyPermission: ['view_pickup_orders', 'manage_pickup_orders', 'create_sale', 'approve_sale_branch'] },
    ],
  },
  {
    id: 'office',
    label: 'اداری',
    icon: 'building',
    defaultPage: 'office',
    children: [
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'office', label: 'تایید سفارش', icon: 'clipboard', permission: 'approve_sale_accounting' },
      { key: 'office-orders', label: 'سفارش‌ها', icon: 'package', anyPermission: ['approve_sale_accounting', 'view_sales'] },
      { key: 'customers', label: 'مشتریان', icon: 'users', permission: 'view_customers' },
      { key: 'rfm', label: 'تحلیل RFM', icon: 'chart', permission: 'view_rfm' },
      { key: 'products', label: 'محصولات', icon: 'package', permission: 'view_products' },
      { key: 'materials', label: 'تایید متریال', icon: 'fabric', permission: 'approve_materials' },
      { key: 'accounting', label: 'حسابداری', icon: 'coins', permission: 'view_accounting' },
      { key: 'factory-accounting', label: 'حسابداری کارخانه', icon: 'factory', permission: 'view_factory_accounting' },
      { key: 'checks', label: 'چک و اقساط', icon: 'receipt', permission: 'view_installments' },
      { key: 'factory', label: 'کارخانه — ساخت', icon: 'wrench', permission: 'view_factory_orders' },
      { key: 'factory-built', label: 'کارخانه — ساخته‌شده', icon: 'check', permission: 'view_factory_orders' },
      { key: 'freight', label: 'کارخانه — باربری', icon: 'truck', permission: 'view_freight_orders' },
      { key: 'warehouse', label: 'انبار', icon: 'package', anyPermission: ['view_warehouse_orders', 'manage_warehouse_orders', 'approve_sale_accounting'] },
      { key: 'filter', label: 'فیلتر', icon: 'search', anyPermission: ['view_accounting', 'approve_sale_accounting', 'view_sales', 'view_customers', 'view_installments'] },
    ],
  },
  {
    id: 'factory',
    label: 'کارخانه',
    icon: 'factory',
    defaultPage: 'factory',
    children: [
      { key: 'notifications', label: 'اعلان‌ها', icon: 'envelope' },
      { key: 'factory', label: 'ساخت', icon: 'wrench', permission: 'view_factory_orders' },
      { key: 'factory-built', label: 'ساخته‌شده‌ها', icon: 'check', permission: 'view_factory_orders' },
      { key: 'freight', label: 'باربری', icon: 'truck', anyPermission: ['view_freight_orders', 'manage_freight_orders'] },
      { key: 'products', label: 'محصولات', icon: 'package', permission: 'view_factory_products' },
      { key: 'materials', label: 'متریال', icon: 'fabric', permission: 'view_materials' },
      { key: 'factory-accounting', label: 'حسابداری', icon: 'coins', permission: 'view_factory_accounting' },
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
