"""Offline-only demo recovery using a previously issued code. Fictional data only."""
import getpass
from pathlib import Path
from src.secure_engine import SecureCore, Denied
uid=input('Demo user ID: ').strip()
code=getpass.getpass('Previously issued recovery code: ')
c=SecureCore(Path('secure_demo.sqlite'))
try:
    result=c.recover_offline(uid,code)
    print('Recovered demo token (shown once):',result['token'])
    print('All previous sessions were revoked. Recovery code consumed.')
except Denied:
    print('Recovery denied. No credential issued.')
finally:c.close()
