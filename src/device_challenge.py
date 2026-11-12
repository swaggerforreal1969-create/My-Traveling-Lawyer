"""Experimental signed device challenge, NOT WebAuthn/passkey authentication.

Provides persistent registered verification keys and short-lived, one-use
step-up challenges. Real passkeys require full WebAuthn RP/origin ceremonies.
"""
from __future__ import annotations
import base64
import secrets
import time
from hashlib import sha256
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

class DeviceDenied(Exception):
    pass


def decode_url64(value, expected):
    if not isinstance(value, str) or not value or len(value) > 200:
        raise DeviceDenied('Invalid proof')
    try:
        raw=base64.b64decode(value + '='*((-len(value)) % 4), altchars=b'-_', validate=True)
    except (ValueError, Exception) as exc:
        raise DeviceDenied('Invalid proof') from exc
    if len(raw) != expected:
        raise DeviceDenied('Invalid proof')
    return raw

class DeviceChallenge:
    PURPOSE='mtl-device-stepup-v1'
    TTL_SECONDS=90

    def __init__(self, core):
        self.core=core
        with core.lock:
            core.db.executescript('''
            CREATE TABLE IF NOT EXISTS device_keys(
                user_id TEXT NOT NULL REFERENCES users(id),
                key_id TEXT NOT NULL PRIMARY KEY,
                key_bytes BLOB NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS device_challenges(
                challenge_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                key_id TEXT NOT NULL REFERENCES device_keys(key_id),
                expires REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0);
            ''')

    def register(self, token, public_key_b64):
        key=decode_url64(public_key_b64,32)
        Ed25519PublicKey.from_public_bytes(key)
        with self.core.authorized_transaction():
            identity=self.core._identity(token)
            key_id=secrets.token_hex(16)
            self.core.db.execute('INSERT INTO device_keys(user_id,key_id,key_bytes) VALUES(?,?,?)',
                (identity['id'],key_id,key))
            self.core._audit(identity['id'],'device.register',key_id)
            return key_id

    def revoke(self, token, key_id):
        """Owner of a demo device key can revoke it; outstanding challenges fail closed."""
        with self.core.authorized_transaction():
            identity=self.core._identity(token)
            cursor=self.core.db.execute(
                'UPDATE device_keys SET revoked=1 WHERE key_id=? AND user_id=? AND revoked=0',
                (key_id,identity['id']))
            if cursor.rowcount != 1:
                raise DeviceDenied('Access denied')
            self.core.db.execute('DELETE FROM device_challenges WHERE key_id=?',(key_id,))
            self.core._audit(identity['id'],'device.revoke',key_id)
            return {'revoked':True}

    def issue(self, token, key_id):
        with self.core.authorized_transaction():
            identity=self.core._identity(token)
            row=self.core.db.execute('SELECT 1 FROM device_keys WHERE key_id=? AND user_id=? AND revoked=0',
                (key_id,identity['id'])).fetchone()
            if not row:raise DeviceDenied('Access denied')
            nonce=secrets.token_urlsafe(32)
            self.core.db.execute('INSERT INTO device_challenges VALUES(?,?,?,?,0)',
                (sha256(nonce.encode()).hexdigest(),identity['id'],key_id,time.time()+self.TTL_SECONDS))
            return {'challenge':nonce,'key_id':key_id,'purpose':self.PURPOSE,'expires_in_seconds':self.TTL_SECONDS}

    def verify(self, token, key_id, nonce, signature_b64):
        if not isinstance(nonce,str) or len(nonce)>128 or len(nonce)<32:
            raise DeviceDenied('Invalid challenge')
        signature=decode_url64(signature_b64,64)
        with self.core.authorized_transaction():
            identity=self.core._identity(token)
            digest=sha256(nonce.encode()).hexdigest()
            row=self.core.db.execute('''SELECT c.expires,c.used,k.key_bytes FROM device_challenges c
                JOIN device_keys k ON k.key_id=c.key_id
                WHERE c.challenge_hash=? AND c.user_id=? AND c.key_id=? AND k.revoked=0''',
                (digest,identity['id'],key_id)).fetchone()
            # Do not consume challenge on failed signature; bounded by 90-second lifetime.
            if not row or row['used'] or row['expires']<=time.time():
                raise DeviceDenied('Invalid challenge')
            message=(self.PURPOSE+'\n'+nonce).encode()
            try:Ed25519PublicKey.from_public_bytes(row['key_bytes']).verify(signature,message)
            except InvalidSignature as exc:raise DeviceDenied('Invalid signature') from exc
            cursor=self.core.db.execute('UPDATE device_challenges SET used=1 WHERE challenge_hash=? AND used=0',(digest,))
            if cursor.rowcount!=1:raise DeviceDenied('Already used')
            self.core._audit(identity['id'],'device.verify',key_id)
            return {'verified':True,'step_up_only':True}
