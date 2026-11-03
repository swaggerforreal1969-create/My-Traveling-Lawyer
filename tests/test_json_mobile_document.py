import json
import unittest
from dataclasses import dataclass
from src.json_mobile_document import render_authenticated_readiness, UnsafeReadinessDocument

@dataclass
class Response:
    status: int
    headers: tuple
    body: bytes

def example(**changes):
    obj = {
        'schema':'mtl.private.readiness.counts.v1',
        'open_tasks':4,
        'past_user_entered_dates_not_court_deadlines':2,
        'research_sources':3,
        'research_needing_procedural_work':2,
        'review_counts':{'needs_additional_review':0,'needs_first_observation':1,'needs_independent_second_review':1,
                         'rejected_by_second_reviewer':0,'two_people_reviewed_unverified':1},
        'legal_source_authenticated':False,'legal_deadlines_verified':False,'court_filing_approved':False,
        'outbound_ai_transmission':False,'human_review_is_legal_verification':False}
    obj.update(changes)
    body=json.dumps(obj).encode()
    return Response(200,(('Content-Type','application/json; charset=utf-8'),('Cache-Control','private, no-store'),
                         ('X-Content-Type-Options','nosniff'),('Content-Length',str(len(body)))),body)

class MobileDocumentTests(unittest.TestCase):
    def test_valid_document_and_headers(self):
        d=render_authenticated_readiness(example())
        self.assertIn(b'Open tasks',d.html)
        self.assertIn(b'NOT court deadlines',d.html)
        self.assertIn(b'No AI transmission',d.html)
        self.assertIn(b'<details>',d.html)
        self.assertEqual(dict(d.headers)['Content-Length'],str(len(d.html)))
        self.assertIn('no-store',dict(d.headers)['Cache-Control'])
    def test_zero_counts(self):
        d=render_authenticated_readiness(example(open_tasks=0,past_user_entered_dates_not_court_deadlines=0,research_sources=0,
                      research_needing_procedural_work=0,review_counts=dict.fromkeys(example().body and json.loads(example().body)['review_counts'],0)))
        self.assertIn(b'Private matter readiness',d.html)
    def test_no_active_content(self):
        h=render_authenticated_readiness(example()).html.lower()
        for bad in (b'<script',b'<iframe',b'<a ',b'<form',b'<img',b'fetch(',b'<input'):
            self.assertNotIn(bad,h)
    def test_deny_unauthorized_response(self):
        r=example();r.status=403
        with self.assertRaises(UnsafeReadinessDocument): render_authenticated_readiness(r)
    def test_deny_extra_private_field(self):
        with self.assertRaises(UnsafeReadinessDocument): render_authenticated_readiness(example(client_name='SECRET'))
    def test_deny_favorable_claims(self):
        for key in ('legal_source_authenticated','legal_deadlines_verified','court_filing_approved','outbound_ai_transmission','human_review_is_legal_verification'):
            with self.subTest(key=key),self.assertRaises(UnsafeReadinessDocument): render_authenticated_readiness(example(**{key:True}))
    def test_deny_bool_as_number(self):
        with self.assertRaises(UnsafeReadinessDocument): render_authenticated_readiness(example(open_tasks=True))
    def test_deny_negative_and_oversized(self):
        for v in (-1,101):
            with self.subTest(v=v),self.assertRaises(UnsafeReadinessDocument): render_authenticated_readiness(example(open_tasks=v))
    def test_deny_unknown_status(self):
        counts=json.loads(example().body)['review_counts'];counts['imaginary_verified']=0
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(example(review_counts=counts))
    def test_deny_mismatched_total(self):
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(example(research_sources=9))
    def test_deny_mismatched_unresolved(self):
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(example(research_needing_procedural_work=1))
    def test_deny_user_dates_exceed_tasks(self):
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(example(past_user_entered_dates_not_court_deadlines=9))
    def test_deny_json_content_type(self):
        r=example();r.headers=(('Content-Type','text/html'),)+r.headers[1:]
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)
    def test_deny_cacheable_response(self):
        r=example();r.headers=tuple((k,'public' if k=='Cache-Control' else v) for k,v in r.headers)
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)
    def test_reject_cache_substring_disguised_as_directive(self):
        r=example()
        r.headers=tuple((k,'not-no-store' if k=='Cache-Control' else v) for k,v in r.headers)
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)

    def test_reject_conflicting_public_or_age_directives(self):
        for value in ('public, no-store', 'max-age=3600, no-store', 'no-store, s-maxage=100'):
            r=example()
            r.headers=tuple((k,value if k=='Cache-Control' else v) for k,v in r.headers)
            with self.subTest(cache=value),self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)

    def test_accept_explicit_private_nostore_directives(self):
        r=example()
        r.headers=tuple((k,'private, no-store, no-cache, must-revalidate' if k=='Cache-Control' else v) for k,v in r.headers)
        self.assertIn(b'Private matter readiness',render_authenticated_readiness(r).html)

    def test_deny_mismatched_length(self):
        r=example();r.headers=tuple((k,'5' if k=='Content-Length' else v) for k,v in r.headers)
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)
    def test_deny_duplicate_headers(self):
        r=example();r.headers+= (('content-type','text/plain'),)
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)
    def test_deny_oversized_body(self):
        r=example();r.body+= b' '*8192
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)
    def test_deny_duplicate_top_level_json_member(self):
        r=example()
        body=r.body.decode('utf-8')
        # A permissive JSON parser would silently accept the final value.
        body=body[:-1]+',"court_filing_approved":false}'
        r.body=body.encode('utf-8')
        r.headers=tuple((k,str(len(r.body)) if k=='Content-Length' else v) for k,v in r.headers)
        with self.assertRaises(UnsafeReadinessDocument):
            render_authenticated_readiness(r)

    def test_deny_duplicate_nested_review_count(self):
        r=example()
        body=r.body.decode('utf-8').replace('"needs_first_observation": 1',
                '"needs_first_observation": 1, "needs_first_observation": 1')
        self.assertNotEqual(body.encode('utf-8'),r.body)
        r.body=body.encode('utf-8')
        r.headers=tuple((k,str(len(r.body)) if k=='Content-Length' else v) for k,v in r.headers)
        with self.assertRaises(UnsafeReadinessDocument):
            render_authenticated_readiness(r)

    def test_deny_malformed_json(self):
        r=example();r.body=b'{' ;r.headers=tuple((k,'1' if k=='Content-Length' else v) for k,v in r.headers)
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(r)
    def test_deny_non_ascii_private_data(self):
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(example(matter_id='secret'))
    def test_deny_missing_flag(self):
        data=json.loads(example().body);data.pop('court_filing_approved')
        with self.assertRaises(UnsafeReadinessDocument):render_authenticated_readiness(example_without_flag(data))

def example_without_flag(data):
    b=json.dumps(data).encode();return Response(200,(('Content-Type','application/json; charset=utf-8'),('Cache-Control','no-store'),
        ('X-Content-Type-Options','nosniff'),('Content-Length',str(len(b)))),b)

if __name__ == '__main__': unittest.main()
