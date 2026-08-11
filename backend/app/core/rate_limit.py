"""Shared limiter instance (docs/SECURITY.md §3). Defined separately from
main.py so routers can import it without a circular import."""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
