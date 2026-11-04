"""Read-only *fictional* signed predecessor envelope from local disk.

Never treat a local filesystem as an independently controlled custody service.
No outbound connection, signer, write API, key storage or trust-pin advancement.
Reject symlinks and file replacement between metadata check and descriptor.
"""
import json
import os
import stat
from pathlib import Path

from .secure_engine import Denied


class OfflineSignedPinFixtureReader:
    def __init__(self, path):
        self.path=Path(path)

    def read_signed_pin(self):
        try:
            info=self.path.lstat()
            if (not stat.S_ISREG(info.st_mode)
                    or not 1<=info.st_size<=4096):
                raise Denied('Invalid offline signed pin file')
            # O_NOFOLLOW blocks a symlink substituted after lstat.
            flags=os.O_RDONLY | getattr(os,'O_NOFOLLOW',0)
            fd=os.open(self.path,flags)
            try:
                current=os.fstat(fd)
                if (not stat.S_ISREG(current.st_mode)
                        or (info.st_dev,info.st_ino)!=(current.st_dev,current.st_ino)
                        or current.st_size!=info.st_size):
                    raise Denied('Signed pin file replaced during read')
                raw=os.read(fd,4097)
                if len(raw)!=info.st_size:
                    raise Denied('Signed pin file changed during read')
            finally:
                os.close(fd)
            value=json.loads(raw.decode('utf-8'))
            if type(value) is not dict:
                raise Denied('Invalid signed pin envelope')
            return value
        except Denied:
            raise
        except (OSError,ValueError,UnicodeError,TypeError) as exc:
            raise Denied('Offline signed pin unavailable') from exc
