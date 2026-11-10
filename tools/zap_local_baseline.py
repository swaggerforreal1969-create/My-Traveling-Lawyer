"""Guarded OWASP ZAP passive baseline: authorized Linux localhost HTTP only.

No HTTP server is started here. The current Tk fictional pilot is OFFLINE.
This must not be pointed at public sites, live clients or disabled legacy code.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
from urllib.error import HTTPError, URLError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    if os.environ.get('MTL_ZAP_TEST_APPROVED') != 'yes-fictional-only':
        raise SystemExit('DENIED: owner-approved fictional-only test required')
    url = os.environ.get('MTL_ZAP_TARGET', '')
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.port is None or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise SystemExit('DENIED: target must be a loopback HTTP base URL with explicit port')
    if not shutil.which('docker'):
        raise SystemExit('NOT RUN: Docker and OWASP ZAP are unavailable')
    try:
        response = build_opener(NoRedirect).open(
            Request(url, method='GET'), timeout=3)
    except HTTPError as error:
        response = error
    except (URLError, TimeoutError) as error:
        raise SystemExit('NOT RUN: approved HTTP test server is not listening') from error
    try:
        if response.headers.get('X-MTL-Fictional-Test-Only') != 'yes':
            raise SystemExit('DENIED: HTTP service did not attest fictional-only test mode')
    finally:
        response.close()
    out = Path(os.environ.get('MTL_ZAP_REPORT_DIR','./zap-reports')).resolve()
    out.mkdir(parents=True,exist_ok=True)
    command = [
        'docker','run','--rm','--network=host',
        '-v',str(out)+':/zap/wrk:rw',
        'ghcr.io/zaproxy/zaproxy:stable',
        'zap-baseline.py','-t',url,'-m','1','-I',
        '-J','zap-local-report.json','-r','zap-local-report.html',
    ]
    print('PASSIVE ZAP baseline on approved fictional loopback HTTP only',flush=True)
    return subprocess.call(command)


if __name__ == '__main__':
    sys.exit(main())
