"""Local-only authenticated attorney research-to-task workflow.

Compose the existing credential/ACL and integrity-checked research services. Every
command is followed by a fresh, minimized readiness snapshot. A successful write
whose subsequent refresh fails MUST NOT be replayed automatically.

This is procedural human review, NOT validation of official legal authority.
No public endpoint, automatic legal deadline, WebAuthn or external AI egress.
"""
from dataclasses import dataclass
from .attorney_journey import AttorneyJourney
from .research_evidence import ResearchEvidence
from .source_observation import SourceObservation
from .second_source_review import SecondSourceReview
from .task_reconciliation import reconcile_task


class RefreshUnresolved(RuntimeError):
    """A committed write succeeded; read-only refresh failed. Never replay write."""

    def __init__(self, operation):
        self.operation = operation
        super().__init__('Post-write readiness refresh unresolved; re-open read-only')


@dataclass(frozen=True)
class WorkflowResult:
    operation: str
    record_id: str
    snapshot: object


class AttorneyResearchWorkflow:
    """End-to-end in-process matter research and attorney task experience."""

    def __init__(self, core):
        self.core = core
        self.journey = AttorneyJourney(core)
        self.evidence = ResearchEvidence(core)
        self.observations = SourceObservation(core)
        self.reviews = SecondSourceReview(core)

    def matters(self, token):
        return self.journey.matters(token)

    def open(self, token, matter_id, *, now=None):
        return self.journey.open(token, matter_id, now=now)

    def _after_commit(self, operation, record_id, token, matter_id, *, now=None):
        try:
            snapshot = self.open(token, matter_id, now=now)
        except Exception as exc:
            # The delegated service has returned successfully; the write was
            # committed. Do not return a response suggesting it may be retried.
            raise RefreshUnresolved(operation) from exc
        return WorkflowResult(operation, record_id, snapshot)

    def add_source(self, token, matter_id, title, url, excerpt, *, now=None):
        result = self.evidence.add(token, matter_id, title, url, excerpt)
        return self._after_commit('source.add', result['id'], token, matter_id, now=now)

    def observe(self, token, matter_id, evidence_id, captured_text, note, *, now=None):
        result = self.observations.capture(token, matter_id, evidence_id, captured_text, note)
        return self._after_commit('source.observe', result['observation_id'], token, matter_id, now=now)

    def second_review(self, token, matter_id, evidence_id, observation_id, decision, note, *, now=None):
        result = self.reviews.record(token, matter_id, evidence_id, observation_id, decision, note)
        return self._after_commit('source.second_review', result['review_id'], token, matter_id, now=now)

    def reconcile_completion(self, token, matter_id, task_id, expected_version):
        """Read-only recovery: no automatic retry after uncertain completion."""
        return reconcile_task(self.core, token, matter_id, task_id, expected_version)

    def complete_task(self, token, matter_id, task_id, expected_version, *, now=None):
        # Use the existing delegated task completion and post-commit refresh;
        # it never retries the write after a failure to refresh.
        return self.journey.complete_and_refresh(token, matter_id, task_id, expected_version, now=now)
