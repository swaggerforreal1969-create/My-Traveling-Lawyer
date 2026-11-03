"""Private, local-only attorney operator session. No HTTP, AI, external calls.

Provides one minimal matter selection -> private mobile readiness ->
authorized reviewer inbox -> human review -> task completion workflow.
All writes delegate to existing independently authorized transactional services.
"""
from dataclasses import dataclass
from .attorney_research_workflow import AttorneyResearchWorkflow
from .secure_engine import Denied, Invalid
from .private_operator_document import render_private_operator


@dataclass(frozen=True)
class OperatorScreen:
    schema: str
    matter_id: str
    readiness_html: bytes
    readiness_headers: tuple
    open_task_count: int
    pending_second_review_count: int
    can_complete_tasks: bool
    legal_deadlines_verified: bool = False
    official_law_verified: bool = False
    court_filing_approved: bool = False
    external_ai_transmission: bool = False


class PrivateAttorneyOperator:
    """Session-less operations: each invocation requires fresh bearer authorization."""

    def __init__(self, core):
        self.core = core
        self.workflow = AttorneyResearchWorkflow(core)

    def matters(self, token):
        return self.workflow.matters(token)

    def select_matter(self, token, matter_id, *, now=None):
        # Hold the local lock across both reauthorized views to avoid showing
        # a task count and review count from different local instants.
        # An external process may still change the DB afterwards: no lease.
        with self.core.lock:
            index = self.workflow.matters(token)
            if not any(m['matter_id'] == matter_id for m in index['matters']):
                raise Denied('Access denied')
            snapshot = self.workflow.open(token, matter_id, now=now)
            view = snapshot.workbench
            if view.get('matter_id') != matter_id:
                raise Invalid('Mismatched matter state')
            if view['can_complete_tasks']:
                inbox = self.workflow.pending_second_reviews(token, matter_id)
                count = len(inbox['items'])
            else:
                count = 0
            return OperatorScreen(
                schema='mtl.private.operator.screen.v1',
                matter_id=matter_id,
                readiness_html=snapshot.readiness_html,
                readiness_headers=snapshot.readiness_headers,
                open_task_count=len(view['open_tasks']),
                pending_second_review_count=count,
                can_complete_tasks=view['can_complete_tasks'],
            )

    def open_accessible_summary(self, token, matter_id, *, now=None):
        """Reauthorize a local screen before rendering a script-free page."""
        return render_private_operator(self.select_matter(token, matter_id, now=now))

    def portfolio(self, token, *, now=None):
        """Fresh, read-only authorized workload across accessible matters."""
        from .private_matter_portfolio import PrivateMatterPortfolio
        return PrivateMatterPortfolio(self).inspect(token, now=now)

    def portfolio_summary(self, token, *, now=None):
        """Safe-to-display minimized portfolio text; no underlying matter IDs."""
        from .private_matter_portfolio import render_portfolio_plain
        return render_portfolio_plain(self.portfolio(token, now=now))

    def reviewer_inbox(self, token, matter_id):
        return self.workflow.pending_second_reviews(token, matter_id)

    def decide_review(self, token, matter_id, evidence_id, observation_id,
                      decision, note, *, now=None):
        return self.workflow.review_from_inbox(
            token, matter_id, evidence_id, observation_id,
            decision, note, now=now)

    def complete_task(self, token, matter_id, task_id, expected_version, *, now=None):
        return self.workflow.complete_if_ready(
            token, matter_id, task_id, expected_version, now=now)

    def reconcile_research(self, token, matter_id, operation, record_id):
        return self.workflow.reconcile_research(token, matter_id, operation, record_id)

    def reconcile_task(self, token, matter_id, task_id, expected_version):
        return self.workflow.reconcile_completion(token, matter_id, task_id, expected_version)
