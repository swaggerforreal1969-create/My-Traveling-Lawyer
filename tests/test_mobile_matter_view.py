"""Security-focused tests for offline attorney mobile rendering (fictional data)."""
import unittest
from html.parser import HTMLParser
from src.mobile_matter_view import render_mobile_brief, InvalidBrief


def sample():
    return {'schema':'mtl.matter.preparation.v1','matter_id':'fictional-001',
            'matter_title':'Invented Hearing', 'matter_version':1,'as_of':'2026-11-03T16:00:00+00:00',
            'notes':[{'text':'Invented client note'}],
            'open_tasks':[{'text':'Review fabricated facts','due_at':'2026-11-01T00:00:00+00:00',
                           'past_user_entered_due_time':True}],
            'research_sources':[{'title':'Imaginary Law', 'url':'https://example.org/invented',
                                 'last_human_assessment':'needs_recheck','software_verified':False}],
            'risk_notices':['Manually verify all court deadlines'],
            'legal_deadlines_verified':False,'legal_authorities_verified_by_software':False,
            'outbound_ai_transmission':False}


class Tags(HTMLParser):
    def __init__(self):
        super().__init__();self.tags=[];self.attrs=[]
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag);self.attrs.append((tag,dict(attrs)))


class MobileMatterViewTests(unittest.TestCase):
    def test_success_contains_read_only_sections(self):
        html=render_mobile_brief(sample())
        self.assertIn('Reveal notes (1)',html)
        self.assertIn('needs_recheck',html)
        self.assertIn('Past user-entered date',html)
    def test_private_sections_initially_collapsed(self):
        p=Tags();p.feed(render_mobile_brief(sample()))
        self.assertEqual(5,p.tags.count('details'))
        self.assertTrue(all('open' not in attrs for tag,attrs in p.attrs if tag=='details'))
    def test_no_script_form_network_or_active_urls(self):
        p=Tags();p.feed(render_mobile_brief(sample()))
        self.assertNotIn('script',p.tags)
        self.assertNotIn('form',p.tags)
        self.assertNotIn('a',p.tags)
        self.assertIn("connect-src 'none'",render_mobile_brief(sample()))
    def test_xss_escaped_in_every_user_field(self):
        s=sample();payload='<img src=x onerror=alert(1)>'
        s['matter_title']=payload;s['notes'][0]['text']=payload
        s['open_tasks'][0]['text']=payload;s['research_sources'][0]['title']=payload
        s['research_sources'][0]['url']='javascript:alert(1)'
        s['risk_notices']=[payload]
        h=render_mobile_brief(s)
        self.assertNotIn('<img',h)
        self.assertNotIn('<img src=',h)
        self.assertIn('&lt;img',h)
        p=Tags();p.feed(h);self.assertNotIn('a',p.tags)
    def test_rejects_flag_claiming_legal_verification(self):
        for flag in ('legal_deadlines_verified','legal_authorities_verified_by_software','outbound_ai_transmission'):
            s=sample();s[flag]=True
            with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_rejects_missing_flag(self):
        s=sample();del s['outbound_ai_transmission']
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_rejects_missing_schema(self):
        s=sample();s['schema']='untrusted'
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_rejects_bad_status(self):
        s=sample();s['research_sources'][0]['last_human_assessment']='verified_by_ai'
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_rejects_false_source_verification(self):
        s=sample();s['research_sources'][0]['software_verified']=True
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_rejects_oversized_fields(self):
        s=sample();s['matter_title']='a'*181
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_rejects_oversized_list(self):
        s=sample();s['notes']=[{'text':'dummy'}]*101
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_rejects_bad_task_flag(self):
        s=sample();s['open_tasks'][0]['past_user_entered_due_time']='yes'
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_bad_non_dict_items(self):
        s=sample();s['notes']=['bad']
        with self.assertRaises(InvalidBrief):render_mobile_brief(s)
    def test_no_network_calls_imports(self):
        import ast,inspect,src.mobile_matter_view as module
        imported={a.names[0].name for a in ast.walk(ast.parse(inspect.getsource(module))) if isinstance(a,ast.Import)}
        self.assertFalse(imported & {'requests','urllib','socket','http','subprocess'})

if __name__=='__main__':unittest.main()
