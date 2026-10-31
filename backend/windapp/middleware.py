"""Restore the real URL when the app runs behind Vercel's catch-all rewrite."""


class RestoreOriginalPathMiddleware:
    """Vercel rewrites every request to /api/index and passes the real address in `?__path=`.

    Django would otherwise try to route '/api/index'. This puts the real path back before URL
    routing, and removes `__path` from the query string so the other parameters are untouched.
    Without `__path` (local development, Docker), it does nothing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        original = request.GET.get("__path")
        if original is not None:
            path = "/" + original.lstrip("/")
            if not path.endswith("/"):
                path += "/"  # every endpoint ends with a slash; avoids a redirect loop
            request.path_info = path
            request.path = path
            query = request.GET.copy()
            query.pop("__path", None)
            request.GET = query
            request.META["QUERY_STRING"] = query.urlencode()
        return self.get_response(request)