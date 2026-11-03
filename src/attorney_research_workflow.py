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
from .task_completion_preflight import prepare_completion
from .research_write_recovery import reconcile_research_write


class RefreshUnresolved(RuntimeError):
    """A committed write succeeded; read-only refresh failed. Never replay write."""

    def __init__(self, operation, record_id=None):
        self.operation = operation
        self.record_id = record_id
        super().__init__('Post-write readiness refresh unresolved; re-open read-only')


@dataclass(frozen=True)
class CompletionAction:
    status: str
    snapshot: object = None
    legal_deadlines_verified: bool = False
    court_filing_approved: bool = False
    independent_audit_verified: bool = False


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
            raise RefreshUnresolved(operation, record_id) from exc
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

    def reconcile_research(self, token, matter_id, operation, record_id):
        """Read-only, actor-specific local recovery of one research write."""
        return reconcile_research_write(self.core, token, matter_id, operation, record_id)

    def reconcile_completion(self, token, matter_id, task_id, expected_version):
        """Read-only recovery: no automatic retry after uncertain completion."""
        return reconcile_task(self.core, token, matter_id, task_id, expected_version)

    def completion_preflight(self, token, matter_id, task_id, expected_version):
        """Minimal editor-only readiness to attempt an atomic task completion."""
        return prepare_completion(self.core, token, matter_id, task_id, expected_version)

    def complete_if_ready(self, token, matter_id, task_id, expected_version, *, now=None):
        """One authorized operator action, not a grant or reusable preflight.

        Preflight and the delegated atomic write share the same local core lock.
        Another local thread cannot complete between those stages. The core
        still checks authorization/version at the actual write; a stale client
        cannot replay a task. Status is not proof of independently held custody.
        """
        with self.core.lock:
            preflight = self.completion_preflight(
                token, matter_id, task_id, expected_version)
            if preflight.status == 'already_completed':
                return CompletionAction('observed_completed_no_write')
            if not preflight.can_attempt_completion:
                return CompletionAction('unresolved_no_write')
            # This is the only completion write in the operator action.
            self.journey.workbench.complete(
                token, matter_id, task_id, expected_version)
        # Do not rerun completion when readiness cannot be refreshed.
        try:
            refreshed = self.open(token, matter_id, now=now)
        except Exception:
            return CompletionAction('committed_refresh_unresolved')
        return CompletionAction('completed_and_refreshed', refreshed)

    def complete_task(self, token, matter_id, task_id, expected_version, *, now=None):
        # Separate the delegated atomic completion from presentation refresh.
        # A committed completion must produce an explicit unresolved outcome if
        # the subsequent read fails, never an invitation to replay the write.
        self.journey.workbench.complete(token, matter_id, task_id, expected_version)
        try:
            return self.open(token, matter_id, now=now)
        except Exception as exc:
            raise RefreshUnresolved('task.complete') from exc
