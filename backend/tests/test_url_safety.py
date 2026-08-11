"""SSRF guard for auto_fetch (docs/SECURITY.md §3)."""
import pytest

from app.core.exceptions import ProviderError
from app.core.url_safety import require_public_http_url


def test_allows_a_real_public_hostname():
    require_public_http_url("https://www.youtube.com/watch?v=jNQXAC9IVRw")


def test_rejects_non_http_scheme():
    with pytest.raises(ProviderError):
        require_public_http_url("file:///etc/passwd")


def test_rejects_loopback_hostname():
    with pytest.raises(ProviderError):
        require_public_http_url("http://localhost:9000/admin")


def test_rejects_loopback_ip_literal():
    with pytest.raises(ProviderError):
        require_public_http_url("http://127.0.0.1:8000/api/health")


def test_rejects_cloud_metadata_endpoint():
    with pytest.raises(ProviderError):
        require_public_http_url("http://169.254.169.254/latest/meta-data/")


def test_rejects_private_rfc1918_address():
    with pytest.raises(ProviderError):
        require_public_http_url("http://10.0.0.5/internal")
