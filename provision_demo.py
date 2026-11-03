"""One-time local fictional credential setup. NEVER publish generated tokens."""
from pathlib import Path
from src.secure_engine import SecureCore
path=Path('secure_demo.sqlite')
c=SecureCore(path)
firm=c.provision_firm('Fictional Demonstration Firm')
uid,token=c.provision_user(firm,'Demo Attorney')
print('DEMO ONLY user ID:',uid)
print('DEMO ONLY token (shown once):',token)
print('LOCAL OFFLINE recovery code (shown once; store separately):',c.issue_recovery_code(token))
print('Open http://127.0.0.1:8766 on THIS computer after python -m src.secure_server')
c.close()
