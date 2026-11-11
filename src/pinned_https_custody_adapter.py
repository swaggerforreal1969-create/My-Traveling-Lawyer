"""Explicitly disabled real-provider HTTPS custody transport adapter.

No network call is possible until BOTH a reviewer-approved endpoint/certificate
pin and enabled=True are injected by an authorized operator. The library never
provisions a service, stores secrets, redirects, retries a write, or clears a
fence. A real provider and independent public-key pin are still required.
"""
import hashlib
import ipaddress
import http.client
import json
import re
import ssl
from urllib.parse import urlsplit
from .secure_engine import Denied

_CERT = re.compile(r"^[0-9a-f]{64}$")
_HOST = re.compile(r"^[a-zA-Z0-9.-]{1,253}$")
_V1_PATHS = {"admit": "/v1/custody/admit",
             "read_head": "/v1/custody/head",
             "read_event": "/v1/custody/event"}
# Contract-only v2 route shapes; actual provider routes require external approval.
_V2_PATHS = {"v2_admit": "/v2/custody/admit",
             "v2_read_latest": "/v2/custody/latest",
             "v2_read_head_at": "/v2/custody/head-at"}
_V2_SCHEMA = "mtl.custody.nonce-bound.v2"


def _reject_nonfinite(value):
    raise ValueError('Non-finite JSON number prohibited')


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
                 enabled=False, timeout_seconds=5, protocol_version="v1"):
        if type(protocol_version) is not str or protocol_version not in ("v1", "v2"):
            raise Denied("Unrecognized custody protocol")
        self._paths = _V1_PATHS if protocol_version == "v1" else _V2_PATHS
        self._protocol_version = protocol_version
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
        try:
            parts=urlsplit(endpoint)
            host=parts.hostname
            port=parts.port
            if host:
                # Reject numeric / IP-literal authorities even when not
                # loopback: remote provider identity must be DNS+TLS pinned.
                try:
                    ipaddress.ip_address(host)
                except ValueError:
                    is_ip=False
                else:
                    is_ip=True
            else:
                is_ip=False
        except ValueError as exc:
            raise Denied("Invalid custody endpoint authority") from exc
        if (parts.scheme!="https" or not host
                or parts.username is not None or parts.password is not None
                or parts.path not in ("", "/") or parts.query or parts.fragment
                or port not in (None,443)
                or is_ip or not _HOST.fullmatch(host)
                or host.startswith(".") or host.endswith(".")
                or ".." in host or host.lower()=="localhost"
                or host.lower().endswith((".local",".localhost",".internal"))
                or "." not in host or host.split(".")[-1].isdigit()
                or any(part.startswith("-") or part.endswith("-")
                       or not part for part in host.split("."))):
            raise Denied("Custody endpoint must be a pinned HTTPS hostname")
        self._host=host
        self._certificate_sha256=certificate_sha256

    def __call__(self, operation, body):
        if not self._enabled or self._host is None:
            raise Denied("External custody is disabled")
        if operation not in self._paths or type(body) is not dict:
            raise Denied("Invalid custody operation")
        if self._protocol_version == "v2" and body.get("schema") != _V2_SCHEMA:
            raise Denied("Version-two custody schema required")
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
            conn.request("POST",self._paths[operation],body=payload,headers={
                "Content-Type":"application/json",
                "Accept":"application/json",
                "Cache-Control":"no-store",
                "Connection":"close"
            })
            response=conn.getresponse()
            if response.status != 200:
                # No redirects, credential forwarding, or disclosure of body.
                raise Denied("Custody provider refused request")
            # Refuse ambiguous duplicate header interpretation and compressed
            # or chunked replies until the provider has an approved policy.
            fields={}
            for name,value in response.getheaders():
                key=name.lower()
                if key in fields:
                    raise Denied("Duplicated custody reply header")
                fields[key]=value
            if any(key in fields for key in ("content-encoding","transfer-encoding")):
                raise Denied("Unsupported custody response encoding")
            length=fields.get("content-length")
            if length is not None:
                if not length.isascii() or not length.isdecimal():
                    raise Denied("Invalid custody reply length")
                if int(length)>16384:
                    raise Denied("Invalid custody reply length")
            content_type=fields.get("content-type","").lower().strip()
            if content_type not in ("application/json",
                                    "application/json; charset=utf-8"):
                raise Denied("Custody provider did not return strict UTF-8 JSON")
            raw=response.read(16385)
            if len(raw)>16384 or (length is not None and len(raw)!=int(length)):
                raise Denied("Custody reply size mismatch")
            result=json.loads(raw.decode("utf-8"),object_pairs_hook=_no_duplicates,
                              parse_constant=_reject_nonfinite)
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
