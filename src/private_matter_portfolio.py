"""Read-only, confidentiality-minimized multi-matter operator portfolio.

No matter titles, source text, task descriptions, raw IDs, bearer tokens,
deadlines, or client data are emitted. Every matter is reauthorized against
the real SecureCore. A changed/revoked matter fails the WHOLE batch closed;
no partial cross-account portfolio is returned. Never legal advice.
"""
from dataclasses import dataclass
from .secure_engine import Denied, Invalid


@dataclass(frozen=True)
class PortfolioItem:
    position: int
    open_tasks: int
    pending_second_reviews: int
    may_act: bool


@dataclass(frozen=True)
class PortfolioSnapshot:
    schema: str
    items: tuple
    total_open_tasks: int
    total_second_reviews: int
    all_matters_authorized: bool = True
    official_law_verified: bool = False
    court_filing_approved: bool = False
    external_ai_transmission: bool = False


class PrivateMatterPortfolio:
    """A single in-process, read-only snapshot with fresh actor ACL checks.

    No externally durable snapshot or across-process lease is claimed.
    The caller MUST refresh after any changes; positions are not write grants.
    """

    def __init__(self, operator):
        self.operator = operator

    def inspect(self, token, *, now=None):
        core = self.operator.core
        with core.authorized_transaction():
            before = self.operator.matters(token)
            if (type(before) is not dict
                    or type(before.get('matters')) is not list
                    or len(before['matters']) > 100
                    or type(before.get('schema')) is not str):
                raise Invalid('Unsafe matter index')
            seen = set()
            items = []
            for i, entry in enumerate(before['matters']):
                if type(entry) is not dict or type(entry.get('matter_id')) is not str:
                    raise Invalid('Unsafe matter listing')
                mid=entry['matter_id']
                if not mid or mid in seen:
                    raise Invalid('Duplicate matter in portfolio')
                seen.add(mid)
                screen = self.operator.select_matter(token, mid, now=now)
                if (screen.matter_id != mid or
                        type(screen.open_task_count) is not int or
                        type(screen.pending_second_review_count) is not int or
                        type(screen.can_complete_tasks) is not bool or
                        screen.open_task_count < 0 or
                        screen.pending_second_review_count < 0 or
                        screen.pending_second_review_count > 10000 or
                        screen.open_task_count > 10000 or
                        any(getattr(screen, field) is not False for field in (
                            'legal_deadlines_verified', 'official_law_verified',
                            'court_filing_approved','external_ai_transmission'))):
                    raise Invalid('Unsafe portfolio state')
                if not screen.can_complete_tasks and screen.pending_second_review_count:
                    raise Denied('Private review counts unavailable to reader')
                items.append(PortfolioItem(i+1,screen.open_task_count,
                                           screen.pending_second_review_count,
                                           screen.can_complete_tasks))
            # Reauthorize all matters AGAIN before publishing a batch result.
            # This detects local changes/revocations between matter readings.
            after = self.operator.matters(token)
            # Compare the entire authorized index, not only matter IDs.
            # A role downgrade or matter-version update with unchanged IDs
            # invalidates displayed may_act flags and workload freshness.
            # Malformed or newly introduced authorization flags also deny.
            if type(after) is not dict or after != before:
                raise Denied('Matter portfolio changed during read')
            return PortfolioSnapshot(
                'mtl.private.portfolio.v1', tuple(items),
                sum(item.open_tasks for item in items),
                sum(item.pending_second_reviews for item in items))


def render_portfolio_plain(snapshot):
    """A private copy-safe textual summary; never output matter identifiers."""
    if (not isinstance(snapshot,PortfolioSnapshot)
            or snapshot.schema!='mtl.private.portfolio.v1'
            or snapshot.all_matters_authorized is not True
            or any(getattr(snapshot,key) is not False for key in (
                'official_law_verified','court_filing_approved',
                'external_ai_transmission'))):
        raise Invalid('Unsafe portfolio summary')
    if (type(snapshot.items) is not tuple
            or len(snapshot.items)>100
            or any(not isinstance(item,PortfolioItem) or
                   type(item.position) is not int or item.position!=i+1 or
                   type(item.open_tasks) is not int or
                   type(item.pending_second_reviews) is not int or
                   type(item.may_act) is not bool or
                   item.open_tasks<0 or item.pending_second_reviews<0 or
                   (not item.may_act and item.pending_second_reviews)
                   for i,item in enumerate(snapshot.items))):
        raise Invalid('Unsafe portfolio entries')
    if (type(snapshot.total_open_tasks) is not int or
            type(snapshot.total_second_reviews) is not int or
            snapshot.total_open_tasks != sum(x.open_tasks for x in snapshot.items)
            or snapshot.total_second_reviews != sum(
                x.pending_second_reviews for x in snapshot.items)):
        raise Invalid('Inconsistent portfolio counts')
    rows = ['PRIVATE ATTORNEY MATTER PORTFOLIO — READ ONLY',
            'Matters: '+str(len(snapshot.items)),
            'Open user-entered tasks: '+str(snapshot.total_open_tasks),
            'Second-human reviews waiting: '+str(snapshot.total_second_reviews)]
    for item in snapshot.items:
        rows.append('Matter '+str(item.position)+': '+str(item.open_tasks)+
                    ' open tasks, '+str(item.pending_second_reviews)+
                    ' reviews; '+('editor' if item.may_act else 'reader'))
    rows.append('Dates are not verified court deadlines. No filing approved.')
    rows.append('No real-law, custody, or independent security approval asserted.')
    return '\n'.join(rows)
