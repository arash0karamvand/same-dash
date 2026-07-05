"""پشتیبانی MariaDB 10.4 (مثلاً XAMPP) برای توسعه محلی."""

import operator

from django.db.backends.mysql.features import DatabaseFeatures as MySQLDatabaseFeatures
from django.utils.functional import cached_property


class DatabaseFeatures(MySQLDatabaseFeatures):
    @cached_property
    def minimum_database_version(self):
        if self.connection.mysql_is_mariadb:
            return (10, 4)
        return (8, 0, 11)

    @cached_property
    def can_return_columns_from_insert(self):
        # MariaDB 10.4 از RETURNING پشتیبانی نمی‌کند.
        if self.connection.mysql_is_mariadb and self.connection.mysql_version < (10, 5):
            return False
        return self.connection.mysql_is_mariadb

    can_return_rows_from_bulk_insert = property(
        operator.attrgetter("can_return_columns_from_insert")
    )
