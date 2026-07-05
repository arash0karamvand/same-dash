"""پیکربندی مسیرهای اصلی پروژه.

تمام endpointهای API زیر پیشوند «/api/» از طریق api.urls سرو می‌شوند.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]
