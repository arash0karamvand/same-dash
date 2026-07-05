from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper

from backend.db_backends.compat_mysql.features import DatabaseFeatures
from backend.db_backends.compat_mysql.schema import DatabaseSchemaEditor


class DatabaseWrapper(MySQLDatabaseWrapper):
    features_class = DatabaseFeatures
    SchemaEditorClass = DatabaseSchemaEditor
