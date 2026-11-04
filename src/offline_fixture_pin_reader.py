"""Restricted offline fixture PIN reader. NOT an independent custody provider.

Used to exercise separate subprocess restarts and simulated pin corruption.
No writer, key handling, HTTP transport, signer, TOFU, or persistence guarantees.
Local file evidence can be rolled back by the same local adversary.
"""
from pathlib import Path
import json
import os
import stat

from .cross_observer_history import CrossObserverRound
from .secure_engine import Denied


class OfflineFixturePinReader:
    def __init__(self, path):
        self.path=Path(path)

    def read_pin(self):
        try:
            info=self.path.lstat()
            if (not stat.S_ISREG(info.st_mode) or
                    info.st_size<1 or info.st_size>2048):
                raise Denied('Offline fixture pin type or length invalid')
            # Reject symbolic links and racey path swaps while reading.
            with self.path.open('rb') as stream:
                current=os.fstat(stream.fileno())
                if (not stat.S_ISREG(current.st_mode) or
                        (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino)
                        or current.st_size!=info.st_size):
                    raise Denied('Offline fixture pin changed during open')
                raw=stream.read(2049)
            if len(raw)!=info.st_size or len(raw)>2048:
                raise Denied('Offline fixture pin length changed during read')
            item=json.loads(raw.decode('utf-8'))
            if (type(item) is not dict or
                    set(item)!={'sequence','signer_a','signer_b','head_a','head_b'}):
                raise Denied('Invalid offline predecessor fixture')
            return CrossObserverRound(**item)
        except Denied:
            raise
        except (OSError,ValueError,UnicodeError,TypeError) as exc:
            raise Denied('Offline fixture pin unavailable or invalid') from exc
