"""Interactive, local-terminal attorney operator over real SecureCore.

No HTTP listener, browser actions, external AI, shell command execution or
automatic retry of uncertain writes. Never prints bearer tokens, case text,
source snippets, URLs, raw IDs or user-entered task descriptions.
This is an experimental offline workflow, not a production client.
"""
from getpass import getpass
from pathlib import Path
import argparse

from .private_attorney_operator import PrivateAttorneyOperator
from .secure_engine import SecureCore, Denied, Invalid, Stale
from .research_evidence import EvidenceInvalid
from .attorney_research_workflow import RefreshUnresolved


class LocalOperatorConsole:
    def __init__(self, core, *, read=None, write=None):
        self.operator = PrivateAttorneyOperator(core)
        self.read = input if read is None else read
        self.write = print if write is None else write

    def _choose(self, title, count, *, portfolio=None):
        self.write(title)
        while True:
            response = self.read(
                'Choose a number, P for private workload, or 0 to cancel: '
                if portfolio is not None else
                'Choose a number, or 0 to cancel: ').strip()
            if response == 'P' and portfolio is not None:
                self.write(portfolio())
                continue
            break
        if response == '0':
            return None
        if not response.isascii() or not response.isdecimal():
            self.write('Invalid selection; no action taken.')
            return None
        number = int(response)
        if not 1 <= number <= count:
            self.write('Invalid selection; no action taken.')
            return None
        return number - 1

    def _confirm(self):
        return self.read('Type YES to perform this one write: ') == 'YES'

    def run(self, token):
        """Handle one authenticated local operator session until user exits."""
        self.write('PRIVATE ATTORNEY OPERATOR — offline procedural work only.')
        self.write('Dates and research are NOT verified law or court filing approval.')
        while True:
            try:
                matter_index = self.operator.matters(token)['matters']
                if not matter_index:
                    self.write('No authorized matters.')
                    return
                self.write('Authorized matters: ' + str(len(matter_index)))
                selection = self._choose(
                    'Select matter by position.',len(matter_index),
                    portfolio=lambda: self.operator.portfolio_summary(token))
                if selection is None:
                    return
                matter_id = matter_index[selection]['matter_id']
                if not self._matter_menu(token, matter_id):
                    return
            except (Denied, Invalid, EvidenceInvalid, Stale):
                self.write('Authorization or state rejected; no automatic write retry.')
                return

    def _matter_menu(self, token, matter_id):
        while True:
            try:
                screen = self.operator.select_matter(token, matter_id)
                self.write('Open tasks: ' + str(screen.open_task_count))
                self.write('Available second-human reviews: ' +
                           str(screen.pending_second_review_count))
                self.write('1 = Review current observation; 2 = Complete task; 3 = Refresh; 0 = Exit')
                choice = self.read('Action: ').strip()
                if choice == '0':
                    return False
                if choice == '3':
                    continue
                if choice == '1':
                    self._review(token, matter_id)
                elif choice == '2':
                    if self._complete(token, matter_id) is False:
                        return False
                else:
                    self.write('Unknown action; no write performed.')
            except RefreshUnresolved as result:
                self.write('COMMITTED, READINESS UNRESOLVED. DO NOT REPEAT THE WRITE.')
                self.write('Use a separate read-only recovery operation with the retained record ID.')
                # Record ID intentionally not printed in local terminal history.
                return False
            except (Denied, Invalid, EvidenceInvalid, Stale):
                self.write('Authorization or current state rejected; re-open read-only.')
                return False

    def _review(self, token, matter_id):
        queue = self.operator.reviewer_inbox(token, matter_id)['items']
        if not queue:
            self.write('No reviewable current observations.')
            return
        pos = self._choose('Current reviewable observations: ' + str(len(queue)), len(queue))
        if pos is None:
            return
        choices = {'1': 'corroborated_manually',
                   '2': 'needs_further_review', '3': 'rejected'}
        self.write('1 = Manually corroborated; 2 = Needs further review; 3 = Rejected')
        decision = choices.get(self.read('Decision: ').strip())
        if decision is None:
            self.write('No review decision recorded.')
            return
        note = self.read('Human review note (15–1200 characters, stored privately): ')
        if not isinstance(note, str) or not 15 <= len(note.strip()) <= 1200:
            self.write('Invalid review note; no write performed.')
            return
        if not self._confirm():
            self.write('Cancelled; no write performed.')
            return
        item = queue[pos]
        result = self.operator.decide_review(
            token, matter_id, item['evidence_id'], item['observation_id'],
            decision, note)
        self.write('Review committed. Private readiness refreshed.')
        if not result.record_id:
            raise Invalid('Unverified review outcome')

    def _complete(self, token, matter_id):
        # Fresh authorized task list; stale commands still reauthorize and
        # compare task version atomically at their actual write boundary.
        view = self.operator.workflow.journey.workbench.matter(token, matter_id)
        if not view['can_complete_tasks']:
            raise Denied('Access denied')
        tasks = view['open_tasks']
        if not tasks:
            self.write('No open tasks.')
            return
        pos = self._choose('Open user-entered tasks: ' + str(len(tasks)), len(tasks))
        if pos is None:
            return
        if not self._confirm():
            self.write('Cancelled; no write performed.')
            return
        task = tasks[pos]
        outcome = self.operator.complete_task_and_refresh_portfolio(
            token, matter_id, task['task_id'], task['version'])
        messages = {
            'completed_and_refreshed': 'Task completed. Private readiness refreshed.',
            'observed_completed_no_write': 'Already completed; no write performed.',
            'unresolved_no_write': 'Task state changed; no write performed.',
            'committed_refresh_unresolved': 'COMMITTED, READINESS UNRESOLVED. DO NOT REPEAT THE WRITE.',
            'portfolio_refresh_unresolved': 'COMMITTED OR OBSERVED, PORTFOLIO UNRESOLVED. DO NOT REPEAT THE WRITE.'
        }
        if outcome.status not in messages:
            raise Invalid('Unexpected completion outcome')
        self.write(messages[outcome.status])
        if outcome.status in ('committed_refresh_unresolved',
                              'portfolio_refresh_unresolved'):
            self.write('Stop this session. Reopen read-only and reconcile before any new write.')
            return False
        if outcome.copy_safe_summary is None or outcome.portfolio is None:
            raise Invalid('Missing verified private portfolio receipt')
        self.write(outcome.copy_safe_summary)
        return True


def main():
    parser = argparse.ArgumentParser(description='Offline experimental attorney operator')
    parser.add_argument('--database', required=True,
                        help='Existing local experimental SQLite database (never a production endpoint)')
    args = parser.parse_args()
    db = Path(args.database)
    if not db.is_file():
        parser.error('Existing local experimental database required')
    token = getpass('Local session bearer token (input hidden): ')
    core = SecureCore(db)
    try:
        LocalOperatorConsole(core).run(token)
    finally:
        core.close()


if __name__ == '__main__':
    main()
