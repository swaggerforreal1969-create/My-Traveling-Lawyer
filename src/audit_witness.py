"""Detached Ed25519 witness for a separately retained audit head.

Requires cryptography. Keep signer private keys OUTSIDE application/database and backups.
This detects rollback only when the verifier has a previously pinned signed checkpoint.
"""
import base64
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':')).encode('utf-8')


def generate_demo_keypair():
    key=Ed25519PrivateKey.generate()
    private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    public=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    return private,base64.b64encode(public).decode()


def sign_head(head,private_pem):
    if head.get('schema')!='mtl.audit.head.v1' or type(head.get('seq')) is not int or head['seq']<0 or not isinstance(head.get('row_hash'),str):
        raise ValueError('Invalid checkpoint head')
    key=serialization.load_pem_private_key(private_pem,password=None)
    if not isinstance(key,Ed25519PrivateKey): raise ValueError('Expected Ed25519 key')
    signature=key.sign(canonical(head))
    return {'head':head,'signature':base64.b64encode(signature).decode(),'algorithm':'Ed25519'}


def verify_pin(current_head,checkpoint,public_b64):
    """Fail closed on rollback/fork; latest signed pin held independently of DB."""
    try:
        if checkpoint['algorithm']!='Ed25519':return False
        public=Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64,validate=True))
        public.verify(base64.b64decode(checkpoint['signature'],validate=True),canonical(checkpoint['head']))
        pinned=checkpoint['head']
        if pinned.get('schema')!='mtl.audit.head.v1' or current_head.get('schema')!='mtl.audit.head.v1':return False
        if type(current_head.get('seq')) is not int or type(pinned.get('seq')) is not int:return False
        if current_head['seq']<pinned['seq']:return False
        if current_head['seq']==pinned['seq'] and current_head.get('row_hash')!=pinned.get('row_hash'):return False
        # For a newer head, the live chain must separately be verified against the pinned hash at seq.
        return current_head['seq']==pinned['seq']
    except (ValueError,KeyError,TypeError):return False
    except Exception:return False


def verify_core_against_pin(core,checkpoint,public_b64):
    """Verify signature, local chain, and exact signed ancestor at pin sequence."""
    try:
        head=core.audit_head()
        pinned=checkpoint['head']
        if not verify_signature(checkpoint,public_b64):return False
        seq=pinned['seq']
        if type(seq) is not int or seq<0 or head['seq']<seq:return False
        if seq==0:return pinned['row_hash']=='GENESIS'
        row=core.db.execute('SELECT row_hash FROM audit_chain WHERE seq=?',(seq,)).fetchone()
        return row is not None and row['row_hash']==pinned['row_hash']
    except Exception:return False


def verify_signature(checkpoint,public_b64):
    try:
        if checkpoint['algorithm']!='Ed25519':return False
        key=Ed25519PublicKey.from_public_bytes(base64.b64decode(public_b64,validate=True))
        key.verify(base64.b64decode(checkpoint['signature'],validate=True),canonical(checkpoint['head']))
        return checkpoint['head'].get('schema')=='mtl.audit.head.v1'
    except Exception:return False


def load_trusted_pin(pin_path, trusted_public_key_path):
    """Load a checkpoint and public key from independently provisioned read-only inputs.

    File paths are supplied by the operator; this DOES NOT establish independent
    custody by itself. Files must be held beyond application-operator control.
    """
    from pathlib import Path
    pin=json.loads(Path(pin_path).read_text(encoding='utf-8'))
    public=Path(trusted_public_key_path).read_text(encoding='ascii').strip()
    if not verify_signature(pin, public):raise ValueError('Untrusted audit checkpoint')
    return pin, public


def validate_trusted_custody(core, pin_path, trusted_public_key_path):
    pin,public=load_trusted_pin(pin_path, trusted_public_key_path)
    if not verify_core_against_pin(core,pin,public):
        raise ValueError('Audit rollback, tampering, or witness mismatch')
    return True
