from django.db.backends.mysql.schema import DatabaseSchemaEditor as MySQLDatabaseSchemaEditor


class DatabaseSchemaEditor(MySQLDatabaseSchemaEditor):
    # MariaDB 10.4 از RENAME COLUMN پشتیبانی نمی‌کند.
    sql_rename_column = (
        "ALTER TABLE %(table)s CHANGE %(old_column)s %(new_column)s %(type)s"
    )
