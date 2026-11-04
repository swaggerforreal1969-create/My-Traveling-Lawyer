"""Authenticated read-only predecessor-pin source for the offline custody boundary.

The caller supplies independently controlled source identity, verification key
through verify_signature, and a read_signed_pin() transport. This module neither
owns keys nor persists/advances pins, connects networks, writes, or clears fences.
Fixture signatures and distinct labels are NOT independent external custody.
"""
import json
from .cross_observer_history import CrossObserverRound
from .independent_checkpoint_boundary import _hex, _identity
from .secure_engine import Denied


class AuthenticatedPinSource:
    """Strict detached-signature contract for a retained cross-observer round."""

    def __init__(self, *, reader, signer_id, verify_signature):
        if (reader is None or not callable(getattr(reader,'read_signed_pin',None))
                or not _identity(signer_id) or not callable(verify_signature)):
            raise Denied('Authenticated predecessor pin source not configured')
        self.reader=reader
        self.signer_id=signer_id
        self.verify_signature=verify_signature

    def read_pin(self):
        try:
            reply=self.reader.read_signed_pin()
        except Exception as exc:
            raise Denied('Signed predecessor read unavailable') from exc
        if (type(reply) is not dict or
                set(reply)!={'schema','signer_id','pin','signature'} or
                reply['schema']!='mtl.custody.predecessor-pin.v1' or
                reply['signer_id']!=self.signer_id or
                type(reply['pin']) is not dict or
                set(reply['pin'])!={'sequence','signer_a','signer_b','head_a','head_b'}
                or not isinstance(reply['signature'],str)
                or len(reply['signature'])<1 or len(reply['signature'])>512):
            raise Denied('Invalid signed predecessor envelope')
        item=reply['pin']
        if (type(item['sequence']) is not int or item['sequence']<0
                or not _identity(item['signer_a']) or
                not _identity(item['signer_b']) or
                item['signer_a']==item['signer_b'] or
                not _hex(item['head_a']) or not _hex(item['head_b'])):
            raise Denied('Malformed signed predecessor identity')
        normalized={
            'schema':reply['schema'],
            'signer_id':self.signer_id,
            'pin':{key:item[key] for key in
                   ('sequence','signer_a','signer_b','head_a','head_b')}
        }
        payload=json.dumps(normalized,sort_keys=True,separators=(',',':'),
                           ensure_ascii=True).encode('ascii')
        try:
            verified=self.verify_signature(
                self.signer_id,payload,reply['signature'])
        except Exception as exc:
            raise Denied('Predecessor pin signature unavailable') from exc
        if verified is not True:
            raise Denied('Predecessor pin signature invalid')
        return CrossObserverRound(**item)
