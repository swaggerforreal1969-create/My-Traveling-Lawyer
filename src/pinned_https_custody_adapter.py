"""Explicitly disabled real-provider HTTPS custody transport adapter.

No network call is possible until BOTH a reviewer-approved endpoint/certificate
pin and enabled=True are injected by an authorized operator. The library never
provisions a service, stores secrets, redirects, retries a write, or clears a
fence. A real provider and independent public-key pin are still required.
"""
import hashlib
import http.client
import json
import re
import ssl
from urllib.parse import urlsplit
from .secure_engine import Denied

_CERT = re.compile(r"^[0-9a-f]{64}$")
_HOST = re.compile(r"^[a-zA-Z0-9.-]{1,253}$")
_PATHS = {"admit": "/v1/custody/admit",
          "read_head": "/v1/custody/head",
          "read_event": "/v1/custody/event"}


def _no_duplicates(pairs):
    out = {}
    for key, val in pairs:
        if key in out:
            raise ValueError("Duplicate JSON field")
        out[key] = val
    return out


class PinnedHTTPSCustodyAdapter:
    """Callable compatible with AuthenticatedCustodyTransport(request=...).

    The certificate pin is a SHA-256 hash of the complete leaf DER cert;
    planned certificate rotation requires independent reauthorization.
    This protects one TLS endpoint's presented certificate, not the
    checkpoint-signing trust root or independent server administration.
    """

    def __init__(self, *, endpoint=None, certificate_sha256=None,
                 enabled=False, timeout_seconds=5):
        self._enabled = enabled is True
        self._host = None
        self._certificate_sha256 = None
        self._timeout = timeout_seconds
        if not self._enabled:
            return
        if (not isinstance(endpoint,str)
                or not isinstance(certificate_sha256,str)
                or _CERT.fullmatch(certificate_sha256) is None
                or type(timeout_seconds) not in (int,float)
                or not 0.5 <= timeout_seconds <= 15):
            raise Denied("Custody TLS endpoint not independently configured")
        parts=urlsplit(endpoint)
        if (parts.scheme!="https" or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment
                or parts.port not in (None,443)
                or not _HOST.fullmatch(parts.hostname)
                or parts.hostname.startswith(".")
                or ".." in parts.hostname
                or parts.hostname.lower() in ("localhost","127.0.0.1")):
            raise Denied("Custody endpoint must be a pinned HTTPS hostname")
        self._host=parts.hostname
        self._certificate_sha256=certificate_sha256

    def __call__(self, operation, body):
        if not self._enabled or self._host is None:
            raise Denied("External custody is disabled")
        if operation not in _PATHS or type(body) is not dict:
            raise Denied("Invalid custody operation")
        try:
            payload=json.dumps(body,sort_keys=True,
                               separators=(",",":"),allow_nan=False).encode("utf-8")
            if len(payload)>16384:
                raise Denied("Custody request exceeds approved limit")
        except (TypeError,ValueError,UnicodeError) as exc:
            raise Denied("Invalid custody request") from exc
        context=ssl.create_default_context()
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        conn=None
        try:
            conn=http.client.HTTPSConnection(self._host,443,
                                             timeout=self._timeout,
                                             context=context)
            conn.connect()  # hostname+chain validated by stdlib TLS
            certificate=conn.sock.getpeercert(binary_form=True)
            if (not isinstance(certificate,bytes)
                    or hashlib.sha256(certificate).hexdigest()!=
                       self._certificate_sha256):
                raise Denied("Custody server certificate pin mismatch")
            conn.request("POST",_PATHS[operation],body=payload,headers={
                "Content-Type":"application/json",
                "Accept":"application/json",
                "Cache-Control":"no-store",
                "Connection":"close"
            })
            response=conn.getresponse()
            if response.status != 200:
                # No redirects, credential forwarding, or disclosure of body.
                raise Denied("Custody provider refused request")
            length=response.getheader("Content-Length")
            if length is not None:
                try:
                    if int(length)<0 or int(length)>16384:
                        raise Denied("Invalid custody reply length")
                except ValueError as exc:
                    raise Denied("Invalid custody reply length") from exc
            if response.getheader("Content-Type","").split(";")[0].strip().lower()!="application/json":
                raise Denied("Custody provider did not return JSON")
            raw=response.read(16385)
            if len(raw)>16384:
                raise Denied("Custody reply exceeds approved limit")
            result=json.loads(raw.decode("utf-8"),object_pairs_hook=_no_duplicates)
            if type(result) is not dict:
                raise Denied("Custody reply must be an object")
            return result
        except Denied:
            raise
        except (OSError,ssl.SSLError,http.client.HTTPException,
                ValueError,UnicodeError,TypeError) as exc:
            raise Denied("Custody transport failed; write outcome uncertain") from exc
        finally:
            if conn is not None:
                conn.close()
