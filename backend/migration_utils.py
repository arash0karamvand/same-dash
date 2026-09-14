"""Reusable operations for the fresh backend schema migration."""


def seed_reference_data(apps, schema_editor):
    def seed(model_name, rows):
        model = apps.get_model("backend", model_name)
        model.objects.bulk_create(
            [
                model(code=code, label=label, sort_order=index)
                for index, (code, label) in enumerate(rows)
            ]
        )

    Branch = apps.get_model("backend", "Branch")
    WorkflowStage = apps.get_model("backend", "WorkflowStage")
    Ledger = apps.get_model("backend", "Ledger")
    Branch.objects.bulk_create(
        [
            Branch(code="branch_1", label="کمرد", color="#6366f1", sort_order=0),
            Branch(code="branch_2", label="پاسداران", color="#10b981", sort_order=1),
        ]
    )
    WorkflowStage.objects.bulk_create(
        [
            WorkflowStage(code="pending_branch", label="صف فروشگاه", sort_order=0),
            WorkflowStage(code="branch_approved", label="صف اداری", sort_order=1),
            WorkflowStage(code="accounting_approved", label="ارسال به کارخانه", sort_order=2),
            WorkflowStage(code="in_production", label="در حال ساخت", sort_order=3),
            WorkflowStage(code="production_done", label="آماده باربری", sort_order=4),
            WorkflowStage(code="in_freight", label="در باربری", sort_order=5),
            WorkflowStage(code="completed", label="تکمیل شده", sort_order=6, is_terminal=True),
        ]
    )
    Ledger.objects.bulk_create(
        [
            Ledger(code="office", name="دفتر اداری", kind="office"),
            Ledger(code="factory", name="دفتر کارخانه", kind="factory"),
        ]
    )
    seed("PaymentMethod", [("cash", "نقدی"), ("card", "کارت‌خوان"), ("check", "چک")])
    seed("PaymentStatus", [("paid", "پرداخت‌شده"), ("unpaid", "پرداخت‌نشده"), ("installment", "قسطی")])
    seed("OrderKind", [("normal", "فروش عادی"), ("pre_invoice", "پیش‌فاکتور"), ("deposit", "بیعانیه")])
    seed("OrderStatus", [("confirmed", "تایید شده"), ("pending", "در انتظار"), ("cancelled", "لغو شده")])
    seed("AccountingMode", [("automatic", "حسابداری خودکار"), ("manual", "حسابداری دستی")])
    seed("InstallmentStatus", [("pending", "در انتظار"), ("paid", "پرداخت‌شده"), ("cancelled", "لغوشده")])
    seed("AttendanceStatus", [("present", "حاضر"), ("absent", "غایب")])
    seed("ApprovalStatus", [("pending", "در انتظار تایید"), ("approved", "تایید شده"), ("rejected", "رد شده")])
    seed("MaterialStatus", [("pending", "در انتظار تایید اداری"), ("approved", "تایید شده"), ("rejected", "رد شده")])
    seed(
        "SmsStatus",
        [
            ("pending", "در صف"),
            ("sent", "ارسال شد"),
            ("failed", "ناموفق"),
            ("mock_sent", "شبیه‌سازی"),
            ("pending_provider_config", "در انتظار تنظیم درگاه"),
        ],
    )
    seed(
        "SmsType",
        [
            ("manual", "دستی"),
            ("welcome", "خوش‌آمدگویی"),
            ("level_up", "ارتقای سطح"),
            ("promotion", "تبلیغاتی"),
            ("birthday", "تبریک تولد"),
            ("order_placed", "ثبت سفارش"),
            ("discount", "تخفیف ویژه"),
            ("reminder", "یادآوری باشگاه"),
        ],
    )
    seed(
        "JournalEntryType",
        [
            ("manual", "دستی"),
            ("sale", "فروش"),
            ("receivable", "دریافتنی"),
            ("payment", "دریافت / پرداخت"),
            ("refund", "برگشت"),
            ("adjustment", "تعدیل"),
            ("other", "سایر"),
        ],
    )
    seed("JournalEntryStatus", [("draft", "پیش‌نویس"), ("posted", "ثبت قطعی"), ("void", "باطل")])

    AuditEntityType = apps.get_model("backend", "AuditEntityType")
    AuditEntityType.objects.bulk_create(
        [
            AuditEntityType(code=code, label=code)
            for code in (
                "Sale",
                "OfficeOrder",
                "FactoryOrder",
                "Customer",
                "JournalEntry",
                "Material",
                "Product",
                "ProductCategory",
                "Seller",
                "StaffAttendance",
                "SaleInstallment",
                "LoyaltyLevel",
                "ReminderCampaign",
                "RoleDefinition",
                "User",
            )
        ]
    )


def install_mysql_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    statements = [
        """
        CREATE TRIGGER trg_journal_post_balanced BEFORE UPDATE ON backend_journalentry
        FOR EACH ROW BEGIN
            DECLARE debit_total DECIMAL(18,0);
            DECLARE credit_total DECIMAL(18,0);
            DECLARE line_count INTEGER;
            IF NEW.status = 'posted' AND OLD.status <> 'posted' THEN
                SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0), COUNT(*)
                INTO debit_total, credit_total, line_count
                FROM backend_journalline WHERE journal_id = NEW.id;
                IF line_count < 2 OR debit_total <> credit_total THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Journal entry is not balanced';
                END IF;
            END IF;
        END
        """,
        """
        CREATE TRIGGER trg_jline_insert_guard BEFORE INSERT ON backend_journalline
        FOR EACH ROW BEGIN
            IF (SELECT status FROM backend_journalentry WHERE id = NEW.journal_id) = 'posted' THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Posted journal is immutable';
            END IF;
        END
        """,
        """
        CREATE TRIGGER trg_jline_update_guard BEFORE UPDATE ON backend_journalline
        FOR EACH ROW BEGIN
            IF (SELECT status FROM backend_journalentry WHERE id = OLD.journal_id) = 'posted' THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Posted journal is immutable';
            END IF;
        END
        """,
        """
        CREATE TRIGGER trg_jline_delete_guard BEFORE DELETE ON backend_journalline
        FOR EACH ROW BEGIN
            IF (SELECT status FROM backend_journalentry WHERE id = OLD.journal_id) = 'posted' THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Posted journal is immutable';
            END IF;
        END
        """,
        """
        CREATE TRIGGER trg_inventory_no_update BEFORE UPDATE ON backend_inventorytransaction
        FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Inventory ledger is append-only'
        """,
        """
        CREATE TRIGGER trg_inventory_no_delete BEFORE DELETE ON backend_inventorytransaction
        FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Inventory ledger is append-only'
        """,
        """
        CREATE TRIGGER trg_wallet_no_update BEFORE UPDATE ON backend_wallettransaction
        FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Wallet ledger is append-only'
        """,
        """
        CREATE TRIGGER trg_wallet_no_delete BEFORE DELETE ON backend_wallettransaction
        FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Wallet ledger is append-only'
        """,
        """
        ALTER TABLE backend_customer
        ADD FULLTEXT INDEX ft_customer_search (full_name, notes)
        """,
        """
        ALTER TABLE backend_product
        ADD FULLTEXT INDEX ft_product_search (name, brand, product_model, description)
        """,
        """
        ALTER TABLE backend_sale
        ADD FULLTEXT INDEX ft_order_search (invoice_number, description)
        """,
        """
        ALTER TABLE backend_auditevent
        ADD FULLTEXT INDEX ft_audit_search (message)
        """,
    ]
    with schema_editor.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def remove_mysql_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    names = [
        "trg_journal_post_balanced",
        "trg_jline_insert_guard",
        "trg_jline_update_guard",
        "trg_jline_delete_guard",
        "trg_inventory_no_update",
        "trg_inventory_no_delete",
        "trg_wallet_no_update",
        "trg_wallet_no_delete",
    ]
    with schema_editor.connection.cursor() as cursor:
        for name in names:
            cursor.execute(f"DROP TRIGGER IF EXISTS {name}")
        for table, index in (
            ("backend_customer", "ft_customer_search"),
            ("backend_product", "ft_product_search"),
            ("backend_sale", "ft_order_search"),
            ("backend_auditevent", "ft_audit_search"),
        ):
            cursor.execute(f"ALTER TABLE {table} DROP INDEX {index}")
