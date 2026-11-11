"""Local, credential-scoped attorney journey for workbench and readiness.

Uses existing in-process ReadinessJSON and strict script-free renderer by default.
No HTTP, external AI, production identity assertion or official-law verification.
"""
from dataclasses import dataclass
import json
from .attorney_workbench import AttorneyWorkbench
from .json_mobile_document import render_authenticated_readiness


class JourneyRejected(ValueError):
    pass


@dataclass(frozen=True)
class MatterJourneySnapshot:
    workbench: dict
    readiness_html: bytes
    readiness_headers: tuple


class AttorneyJourney:
    """Provide authorized matter list, snapshot and task-completion refresh."""

    def __init__(self, core, *, readiness=None):
        self.workbench = AttorneyWorkbench(core)
        if readiness is None:
            # Import only in approved assembled project. Missing modules must not
            # silently downgrade to synthetic readiness or unverified legal claims.
            from .readiness_json import ReadinessJSON
            readiness = ReadinessJSON(core)
        self.readiness = readiness

    def matters(self, token):
        return self.workbench.matters(token)

    @staticmethod
    def _validate_workbench(view, matter_id):
        if (type(view) is not dict or view.get('schema') != 'mtl.private.workbench.matter.v1'
                or view.get('matter_id') != matter_id
                or any(view.get(k) is not False for k in ('legal_deadlines_verified',
                    'legal_sources_authenticated', 'court_filing_approved', 'outbound_ai_transmission'))):
            raise JourneyRejected('Unsafe or mismatched matter state')

    def open(self, token, matter_id, *, now=None):
        # Component reads share one cross-process authorization snapshot.
        with self.workbench.core.authorized_transaction():
            return self._open_authorized(token, matter_id, now=now)

    def _open_authorized(self, token, matter_id, *, now=None):
        view = self.workbench.matter(token, matter_id, now=now)
        self._validate_workbench(view, matter_id)
        response = self.readiness.prepare(token, matter_id, now=now)
        rendered = render_authenticated_readiness(response)
        # JSON is already checked for duplicate keys and legal assertions by
        # the renderer. Reconcile its task counts against this matter's real
        # authorized queue before presenting two supposedly matching views.
        summary = json.loads(response.body)
        tasks = view['open_tasks']
        if (summary['open_tasks'] != len(tasks) or
                summary['past_user_entered_dates_not_court_deadlines'] !=
                sum(t['past_user_entered_date'] is True for t in tasks)):
            raise JourneyRejected('Readiness and task queue disagree')
        # Recheck that authorization has not been removed since the snapshot.
        latest = self.workbench.matter(token, matter_id, now=now)
        self._validate_workbench(latest, matter_id)
        if latest != view:
            raise JourneyRejected('Matter changed during readiness preparation')
        return MatterJourneySnapshot(latest, rendered.html, rendered.headers)

    def complete_and_refresh(self, token, matter_id, task_id, expected_version, *, now=None):
        # No implicit retry after a committed write if refresh fails. Caller can
        # inspect current state read-only with a fresh open request.
        self.workbench.complete(token, matter_id, task_id, expected_version)
        return self.open(token, matter_id, now=now)
