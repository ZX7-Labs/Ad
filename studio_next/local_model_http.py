"""Bounded local-model transport: never use ambient proxies or redirects."""
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Local model redirects are not permitted")


def urlopen(request, *, timeout):
    url = request.full_url if hasattr(request, "full_url") else request
    parts = urlsplit(url)
    if (parts.scheme != "http" or parts.hostname not in
            ("localhost", "127.0.0.1", "::1") or parts.username or
            parts.password or parts.query or parts.fragment):
        raise ValueError("Model transport requires a local unauthenticated endpoint")
    # A per-call opener avoids mutating the process-global urllib opener.
    return build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout)
