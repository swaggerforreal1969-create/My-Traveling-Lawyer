"""Offline-only adapter for preapproved fictional AI preflight packets.

This is NOT a provider transport. It cannot contact any external service.
It validates a complete exact-schema packet, maps it to a bounded fixed-shape
request and returns serialized bytes for inspection with no credentials.
"""
from hashlib import sha256
import json

from .ai_outbound_boundary import ConfidentialAIRequest


class ProviderPacketDenied(ValueError):
    pass


class OfflineProviderAdapter:
    MAX_BYTES = 1024
    FIELDS = frozenset({
        'schema', 'template_id', 'prompt', 'prompt_sha256', 'fictional_only',
        'contains_matter_data', 'contains_user_supplied_text', 'network_sent',
        'provider_configured', 'legal_advice',
    })

    def prepare(self, packet, *, network_enabled=False, provider_credentials=None,
                endpoint=None, user_content=None):
        # The API surface intentionally has NO transport, HTTP client or callable
        # provider hook. Additional data is rejected rather than merged.
        if network_enabled is not False or provider_credentials is not None or endpoint is not None or user_content is not None:
            raise ProviderPacketDenied('Transport, credentials and extra content are prohibited')
        if not isinstance(packet, dict) or frozenset(packet) != self.FIELDS:
            raise ProviderPacketDenied('Unexpected preflight packet fields')
        exact = {
            'schema': ConfidentialAIRequest.SCHEMA,
            'fictional_only': True,
            'contains_matter_data': False,
            'contains_user_supplied_text': False,
            'network_sent': False,
            'provider_configured': False,
            'legal_advice': False,
        }
        for field, value in exact.items():
            if type(packet[field]) is not type(value) or packet[field] != value:
                raise ProviderPacketDenied('Invalid preflight safety assertion')
        template = packet['template_id']
        if not isinstance(template, str) or template not in ConfidentialAIRequest.TEMPLATES:
            raise ProviderPacketDenied('Unapproved template')
        prompt = ConfidentialAIRequest.TEMPLATES[template]
        digest = sha256(prompt.encode('utf-8')).hexdigest()
        if type(packet['prompt']) is not str or packet['prompt'] != prompt:
            raise ProviderPacketDenied('Modified or user-supplied prompt')
        if type(packet['prompt_sha256']) is not str or packet['prompt_sha256'] != digest:
            raise ProviderPacketDenied('Prompt digest mismatch')
        body = json.dumps({'messages': [{'role': 'user', 'content': prompt}],
                           'model': 'NOT_CONFIGURED'},
                          sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
        if len(body) > self.MAX_BYTES:
            raise ProviderPacketDenied('Packet exceeds strict size bound')
        return {
            'schema': 'mtl.ai.provider.offline_review.v1',
            'body': body,
            'body_sha256': sha256(body).hexdigest(),
            'size_bytes': len(body),
            'network_sent': False,
            'provider_configured': False,
            'transport_available': False,
            'contains_matter_data': False,
            'fictional_only': True,
            'notice': 'OFFLINE ONLY: not sent, not provider-authorized, no client data',
        }
