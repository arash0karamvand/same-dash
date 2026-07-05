"""تمام endpointهای API پروژه — پیشوند «/api/» در backend/urls.py."""

from django.urls import path

from api.views import (
    accounting,
    attendance,
    audit_logs,
    auth,
    birthday_sms,
    customers,
    dashboard,
    installments,
    loyalty_levels,
    org_chart,
    products,
    reminder_sms,
    role_definitions,
    sales,
    sms,
    sms_club,
    staff,
    wallet,
)

urlpatterns = [
    # --- Auth (/api/auth/) ---
    path("auth/login/", auth.login, name="auth-login"),
    path("auth/logout/", auth.logout, name="auth-logout"),
    path("auth/me/", auth.me, name="auth-me"),
    path("auth/roles/", auth.role_list, name="auth-roles"),
    path("auth/users/", auth.user_list, name="auth-users"),
    path("auth/users/<int:pk>/", auth.user_detail, name="auth-user-detail"),
    path("auth/users/<int:pk>/reset-password/", auth.user_reset_password, name="auth-user-reset-password"),
    path("auth/users/<int:pk>/deactivate/", auth.user_deactivate, name="auth-user-deactivate"),
    path("auth/assign-role/", auth.assign_role, name="auth-assign-role"),
    path("auth/change-password/", auth.change_password, name="auth-change-password"),
    path("auth/reset-business-data/", auth.reset_business_data, name="auth-reset-business-data"),
    path("auth/permissions/", role_definitions.permission_matrix, name="auth-permissions"),
    path("auth/role-definitions/", role_definitions.role_definition_list, name="auth-role-definitions"),
    path(
        "auth/role-definitions/<slug:slug>/",
        role_definitions.role_definition_detail,
        name="auth-role-definition-detail",
    ),
    path("auth/org-ranks/", role_definitions.org_rank_list, name="auth-org-ranks"),
    path("auth/org-ranks/<int:pk>/", role_definitions.org_rank_detail, name="auth-org-rank-detail"),
    path("org-chart/", org_chart.org_chart, name="org-chart"),

    # --- Dashboard ---
    path("dashboard/summary/", dashboard.dashboard_summary, name="dashboard-summary"),

    # --- Customers ---
    path("customers/", customers.customer_list, name="customer-list"),
    path(
        "customers/recalculate-all-levels/",
        customers.recalculate_all_levels,
        name="customer-recalculate-all",
    ),
    path("customers/top-buyers/", customers.customer_top_buyers, name="customer-top-buyers"),
    path("customers/<int:pk>/", customers.customer_detail, name="customer-detail"),
    path(
        "customers/<int:pk>/recalculate-level/",
        customers.recalculate_level,
        name="customer-recalculate-level",
    ),
    path(
        "customers/<int:pk>/history/",
        customers.customer_history,
        name="customer-history",
    ),
    path(
        "customers/<int:pk>/wallet/",
        wallet.customer_wallet,
        name="customer-wallet",
    ),

    # --- Sales ---
    path("sales/reports/daily/", sales.sales_daily_report, name="sales-daily-report"),
    path("sales/reports/monthly/", sales.sales_monthly_report, name="sales-monthly-report"),
    path("sales/reports/yearly/", sales.sales_yearly_report, name="sales-yearly-report"),
    path("sales/employee-ranking/", sales.employee_ranking, name="sales-employee-ranking"),
    path("sales/", sales.sale_list, name="sale-list"),
    path(
        "sales/<int:pk>/record-payment/",
        sales.sale_record_payment,
        name="sale-record-payment",
    ),
    path("sales/<int:pk>/", sales.sale_detail, name="sale-detail"),

    # --- Installments & Checks ---
    path("installments/", installments.installment_list, name="installment-list"),
    path("installments/checks-report/", installments.checks_monthly_report, name="checks-report"),
    path("installments/<int:pk>/pay/", installments.installment_pay, name="installment-pay"),
    path("installments/<int:pk>/", installments.installment_detail, name="installment-detail"),

    # --- Attendance ---
    # --- Products ---
    path("products/categories/", products.category_list, name="product-category-list"),
    path("products/categories/<int:pk>/", products.category_detail, name="product-category-detail"),
    path("products/", products.product_list, name="product-list"),
    path("products/<int:pk>/", products.product_detail, name="product-detail"),
    path("audit-logs/", audit_logs.audit_log_list, name="audit-log-list"),
    path("staff/", staff.staff_list, name="staff-list"),
    path("staff/<int:pk>/", staff.staff_detail, name="staff-detail"),
    path("attendance/today/", attendance.attendance_today, name="attendance-today"),
    path("attendance/check-in/", attendance.attendance_check_in, name="attendance-check-in"),
    path("attendance/check-out/", attendance.attendance_check_out, name="attendance-check-out"),
    path("attendance/<int:pk>/approve/", attendance.attendance_approve, name="attendance-approve"),
    path("attendance/", attendance.attendance_list, name="attendance-list"),
    path("attendance/<int:pk>/", attendance.attendance_detail, name="attendance-detail"),

    # --- Accounting ---
    path("accounting/", accounting.entry_list, name="accounting-list"),
    path("accounting/summary/", accounting.summary, name="accounting-summary"),
    path("accounting/sales-report/", accounting.sales_report, name="accounting-sales-report"),
    path("accounting/bulk-approve/", accounting.bulk_approve, name="accounting-bulk-approve"),
    path(
        "accounting/customer/<int:customer_id>/",
        accounting.customer_accounting,
        name="accounting-customer",
    ),
    path(
        "accounting/<int:pk>/approve/",
        accounting.entry_approve,
        name="accounting-approve",
    ),
    path("accounting/<int:pk>/", accounting.entry_detail, name="accounting-detail"),

    # --- Loyalty Levels ---
    path("loyalty-levels/", loyalty_levels.level_list, name="loyalty-level-list"),
    path("loyalty-levels/<int:pk>/", loyalty_levels.level_detail, name="loyalty-level-detail"),

    # --- SMS ---
    path("sms/logs/", sms.sms_logs, name="sms-logs"),
    path("sms/send/", sms.sms_send, name="sms-send"),
    path("sms/send-to-level/", sms.sms_send_to_level, name="sms-send-to-level"),
    path("sms/send-to-all/", sms.sms_send_to_all, name="sms-send-to-all"),
    path("sms/birthday/settings/", birthday_sms.birthday_settings, name="sms-birthday-settings"),
    path("sms/birthday/preview/", birthday_sms.birthday_preview, name="sms-birthday-preview"),
    path("sms/birthday/exclude/", birthday_sms.birthday_exclude, name="sms-birthday-exclude"),
    path(
        "sms/birthday/exclude/<int:customer_id>/",
        birthday_sms.birthday_unexclude,
        name="sms-birthday-unexclude",
    ),
    path("sms/birthday/send/", birthday_sms.birthday_send, name="sms-birthday-send"),
    path("sms/club/settings/", sms_club.club_settings, name="sms-club-settings"),
    path("sms/club/send-discount/", sms_club.club_send_discount, name="sms-club-send-discount"),
    path("sms/club/discount-preview/", sms_club.club_discount_preview, name="sms-club-discount-preview"),
    path("sms/reminders/", reminder_sms.reminder_list, name="sms-reminder-list"),
    path("sms/reminders/preview/", reminder_sms.reminder_preview, name="sms-reminder-preview"),
    path("sms/reminders/<int:pk>/", reminder_sms.reminder_detail, name="sms-reminder-detail"),
    path("sms/reminders/<int:pk>/send/", reminder_sms.reminder_send, name="sms-reminder-send"),
]
