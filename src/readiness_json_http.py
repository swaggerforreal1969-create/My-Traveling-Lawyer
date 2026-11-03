"""Optional, isolated localhost JSON endpoint using established ticket and HTTP gates.

No public binding, ticket minting over HTTP, production service, or external egress.
The HTTP route intentionally remains the one established private readiness route;
this server has a fixed JSON representation, never content-negotiated by a client.
"""
from .readiness_loopback_http import LoopbackReadinessServer
from .readiness_json import ReadinessJSON


class LoopbackJSONReadinessServer(LoopbackReadinessServer):
    """Use real bearer + single-use ticket authorization for minimal JSON output."""

    def __init__(self, core, address=('127.0.0.1', 0), *, max_connections=8, idle_seconds=2.0):
        super().__init__(core, address=address, max_connections=max_connections,
                         idle_seconds=idle_seconds)
        # This is an in-process, immutable representation choice fixed at server
        # construction, not a request-controlled switch. Parent handler continues
        # to authenticate and atomically consume the same matter-scoped ticket.
        self.broker.gateway = ReadinessJSON(core)
