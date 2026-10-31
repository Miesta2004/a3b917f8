"""Vercel entry point: exposes the Django WSGI app as `app`.

Vercel rewrites every request to /api/index (see vercel.json), so Django would see
'/api/index' instead of the real address. vercel.json therefore passes the original path
in a `__path` query parameter, and the wrapper below restores it before Django routes.
"""
import os
import sys
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "windapp.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

django_app = get_wsgi_application()


def app(environ, start_response):
    params = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    original = next((value for key, value in params if key == "__path"), None)
    if original is not None:
        path = "/" + original.lstrip("/")
        if not path.endswith("/"):
            path += "/"  # every endpoint ends with a slash; avoids a redirect loop
        environ["PATH_INFO"] = path
        environ["QUERY_STRING"] = urlencode([(k, v) for k, v in params if k != "__path"])
    return django_app(environ, start_response)