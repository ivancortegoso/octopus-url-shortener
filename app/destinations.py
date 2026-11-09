"""Rules about where this service is willing to send visitors.

A URL shortener lends its domain's credibility to whatever it points at, so the
destination is checked before a link is created. What is refused here are addresses that
belong to the machine or the network the service runs on: a short link that resolves to
a private address lets someone use a trusted domain to walk a visitor into their own
internal network, and one pointing at the service itself builds redirect chains.

The check reads the host as written. A public domain name that resolves to a private
address is not caught; doing that reliably means resolving at redirect time, which does
not survive DNS rebinding either. The gain here is closing the direct case cheaply.
"""

import ipaddress
from urllib.parse import urlparse

LOCAL_HOSTNAMES = frozenset({"localhost", "0.0.0.0", "[::]"})
LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")


class UnsafeDestinationError(Exception):
    """Raised when a URL names somewhere the service refuses to redirect to."""


def ensure_safe_destination(url: str, service_origin: str) -> None:
    """Raise if the URL points at the local network, the machine, or the service itself."""
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise UnsafeDestinationError("The URL names no host.")

    if host in LOCAL_HOSTNAMES or host.endswith(LOCAL_SUFFIXES):
        raise UnsafeDestinationError(f"{host!r} names the machine running this service.")

    address = _parse_ip_address(host)
    if address is not None and not address.is_global:
        raise UnsafeDestinationError(
            f"{host!r} is not a publicly routable address, so a visitor following this "
            "link would be sent into a private network."
        )

    if host == (urlparse(service_origin).hostname or "").lower():
        raise UnsafeDestinationError(
            "The URL points at this service, which would create a redirect chain."
        )


def _parse_ip_address(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Return the host as an IP address, or None when it is a domain name."""
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None
