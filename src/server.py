"""Only supported web entrypoint: v0.4 authenticated, loopback-only API."""
from .secure_server import run
if __name__=='__main__': run()
