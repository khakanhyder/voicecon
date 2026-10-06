"""
The marketing blog.

* ``admin.router`` — the console's blog section (``/api/v1/admin/blog``) and
  ``/api/v1/admin/me``. Open to blog editors/viewers as well as platform
  admins; each route names its own guard.
* ``public.router`` — the website's read-only API (``/api/v1/blog``).
"""
from . import admin, public

__all__ = ["admin", "public"]
