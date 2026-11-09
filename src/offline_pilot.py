"""Fictional-only, offline local Tk attorney pilot lifecycle.

No HTTP server, provider network, live client data, privileged permissions,
automatic recovery, or modification of an existing database. NOT a release
entrypoint. Secrets are shown once to the local operator at initialization.
"""
from __future__ import annotations

import argparse
from getpass import getpass
import os
from pathlib import Path

from .secure_engine import SecureCore, Denied, Invalid
from .durable_local_write_fence import LocalWriteFence
from .attorney_research_workflow import AttorneyResearchWorkflow


BANNER = ('OFFLINE FICTIONAL PILOT ONLY — NOT FOR CLIENT DATA, '
          'LEGAL ADVICE, COURT FILING OR PRODUCTION')


def initialize_fictional_pilot(database: Path):
    """Create a new, private SQLite pilot and one author/reviewer workflow.

    Returns short-lived caller-owned tokens for one-time local display.
    Existing files, existing symlinks and missing parent directories deny.
    """
    path = Path(database).expanduser()
    if path.exists() or path.is_symlink():
        raise Denied('Pilot database already exists; no overwrite permitted')
    if not path.parent.is_dir():
        raise Denied('Create the destination directory separately')
    # Restrictive umask also covers SQLite's lock/journal and the fence sidecar.
    old_umask = os.umask(0o077)
    reserved = False
    core = None
    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, 'O_NOFOLLOW'):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(path), flags, 0o600)
        os.close(fd)
        reserved = True
        core = SecureCore(path)
        firm = core.provision_firm('Fictional Pilot Legal Office')
        editor_id, editor_token = core.provision_user(firm, 'Fictional Attorney')
        reviewer_id, reviewer_token = core.provision_user(
            firm, 'Independent Fictional Reviewer')
        matter = core.create_matter(editor_token, 'Fictional Research Matter')
        matter_id = matter['id']
        core.grant(editor_token, matter_id, reviewer_id, 'editor', 1)
        core.create_task(editor_token, matter_id,
                         'Fictional manual legal research check',
                         '2030-01-01T00:00:00Z')
        workflow = AttorneyResearchWorkflow(core)
        evidence = workflow.evidence.add(
            editor_token, matter_id, 'Fictional Source Title',
            'https://example.org/fictional-only',
            'Synthetic example excerpt, not actual legal authority')
        workflow.observations.capture(
            editor_token, matter_id, evidence['id'],
            'Fictional observation',
            'Human-created imaginary observation for local pilot')
        if not core.verify_audit():
            raise Denied('Pilot audit verification failed')
        # Bind a real crash-persistent local write-fence before any GUI action.
        fence = LocalWriteFence(path)
        if fence.is_pending():
            raise Denied('Fresh pilot has an unexpected pending write')
        return {'editor_token': editor_token,
                'reviewer_token': reviewer_token,
                'database': path}
    except Exception:
        # Never alter an existing database; only cleanup the path reserved by
        # THIS initializer. Failed setups must not leave usable credentials.
        if core is not None:
            core.close()
            core = None
        if reserved:
            for filename in (str(path), str(path) + '.write-fence.sqlite3',
                             str(path) + '-journal', str(path) + '-wal',
                             str(path) + '-shm'):
                try:
                    os.unlink(filename)
                except FileNotFoundError:
                    pass
        raise
    finally:
        if core is not None:
            core.close()
        os.umask(old_umask)


def open_fictional_pilot(database: Path, token: str, *, run_mainloop=True):
    """Open an existing local GUI, with independent current token check."""
    path = Path(database).expanduser()
    if not path.is_file() or path.is_symlink():
        raise Denied('An existing regular fictional pilot database is required')
    if not token or not isinstance(token, str):
        raise Denied('Local credential required')
    core = SecureCore(path)
    try:
        # Verify authorization before allocating a native window. A pending
        # write fence is NOT cleared; GUI restart handles read-only recovery.
        from .private_attorney_operator import PrivateAttorneyOperator
        PrivateAttorneyOperator(core).matters(token)
        from .local_operator_gui import launch_gui
        root = launch_gui(core, token, run_mainloop=run_mainloop)
        if not run_mainloop:
            # Explicit lifetime ownership for headless/native acceptance.
            # Callers must destroy root and close core.
            return root, core
        return None
    except Exception:
        core.close()
        raise
    finally:
        if run_mainloop:
            core.close()



def inspect_fictional_pilot(database: Path, token: str):
    """Reauthorize a minimized workload readback without opening a GUI.

    Never clears an unresolved write fence or attempts a task/review write.
    Existing local databases are experimental, not independently trusted.
    """
    path = Path(database).expanduser()
    if not path.is_file() or path.is_symlink():
        raise Denied('An existing regular fictional pilot database is required')
    if not token or not isinstance(token, str):
        raise Denied('Local credential required')
    core = SecureCore(path)
    try:
        from .private_attorney_operator import PrivateAttorneyOperator
        # Do not extend the user's idle deadline merely by checking records.
        with core.passive_authorization():
            if not core.verify_audit():
                raise Denied('Local audit verification failed')
            pending = LocalWriteFence(path).is_pending()
            summary = PrivateAttorneyOperator(core).portfolio_summary(token)
            if not core.verify_audit():
                raise Denied('Local audit verification failed')
        return {'summary': summary, 'write_unresolved': pending}
    finally:
        core.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=BANNER)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('init', 'open', 'status'):
        sub.add_parser(name).add_argument('--database', type=Path, required=True)
    args = parser.parse_args(argv)
    print(BANNER)
    if args.command == 'init':
        result = initialize_fictional_pilot(args.database)
        print('New fictional pilot created; credentials appear ONCE here.')
        print('Fictional attorney token:', result['editor_token'])
        print('Fictional reviewer token:', result['reviewer_token'])
        print('Store these separately; never paste them into chat or logs.')
        print('Next: python -m src.offline_pilot open --database',
              result['database'])
    elif args.command == 'status':
        token = getpass('Local fictional pilot token (hidden): ')
        try:
            report = inspect_fictional_pilot(args.database, token)
        except (Denied, Invalid):
            print('Saved-work check denied or unavailable. No task/review write attempted.')
            return 1
        print(report['summary'])
        if report['write_unresolved']:
            print('LOCAL WRITE UNRESOLVED — do not repeat an earlier action.')
        else:
            print('No pending local write fence detected; independent custody unverified.')
    else:
        token = getpass('Local fictional pilot token (hidden): ')
        try:
            open_fictional_pilot(args.database, token)
        except Denied:
            print('Login denied or local pilot unavailable. No write attempted.')
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
