"""SSRF guard for any URL this backend fetches on the operator's behalf
(docs/SECURITY.md §3). The main call site is `auto_fetch`
(app/services/url_downloader.py), where the URL is operator-supplied —
authenticated, but still worth defending in depth against a compromised
or malicious admin/reviewer account pointing the fetch at internal
infrastructure (localhost services, cloud metadata endpoints, RFC1918
ranges) rather than a real public reel."""
import ipaddress
import socket
from urllib.parse import urlparse

from app.core.exceptions import ProviderError

_ALLOWED_SCHEMES = {"http", "https"}


def require_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ProviderError(f"Refusing to fetch {url!r}: only http/https URLs are allowed.")
    if not parsed.hostname:
        raise ProviderError(f"Refusing to fetch {url!r}: no hostname found.")

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise ProviderError(f"Could not resolve hostname for {url!r}: {exc}") from exc

    for family, _, _, _, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ProviderError(
                f"Refusing to fetch {url!r}: resolves to a non-public address ({ip}). "
                "This looks like it points at internal infrastructure rather than a public reel."
            )
