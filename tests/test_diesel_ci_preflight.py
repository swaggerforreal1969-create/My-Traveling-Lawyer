"""Fast preflight tests before native runners, no network and no app writes."""
import unittest
from tools.diesel_ci_preflight import get_plan

QUEUE={"version":1,"release":"NO_GO","recurring_enabled":False,
       "tasks":[{"state":"VERIFIED"},{"state":"UNRESOLVED"},
                {"state":"BLOCKED"},{"state":"BLOCKED"}]}

class Preflight(unittest.TestCase):
    def test_infrastructure_change_does_not_queue_windows_build(self):
        p=get_plan(["docs/DIESEL_CUSTOMER_QUEUE.json",".github/workflows/x.yml"],
                   http_source_present=False,queue=QUEUE)
        self.assertFalse(p["windows_runner_required"])
        self.assertFalse(p["customer_source_changed"])
        self.assertEqual(p["classification"],"INFRA_ONLY_REUSE_CUSTOMER_EVIDENCE")

    def test_windows_changed_source_requests_windows_runner(self):
        p=get_plan(["tools/windows_fictional_gui.py"],http_source_present=False,queue=QUEUE)
        self.assertTrue(p["windows_runner_required"])
        self.assertTrue(p["customer_source_changed"])

    def test_missing_restricted_http_is_blocked_not_pass(self):
        p=get_plan([],http_source_present=False,queue=QUEUE)
        self.assertEqual(p["security"]["status"],"BLOCKED_REQUIRED_RESTRICTED_SOURCE")
        self.assertFalse(p["security"]["release_eligible"])

    def test_present_http_source_still_not_signoff(self):
        p=get_plan([],http_source_present=True,queue=QUEUE)
        self.assertEqual(p["security"]["status"],"UNRESOLVED_REQUIRES_AUTHORIZED_SECURITY_RUN")
        self.assertFalse(p["security"]["release_eligible"])

    def test_recurring_runner_refused(self):
        q={**QUEUE,"recurring_enabled":True}
        with self.assertRaises(ValueError):
            get_plan([],http_source_present=False,queue=q)

    def test_unexpected_queue_rejected(self):
        with self.assertRaises(ValueError):
            get_plan([],http_source_present=False,queue={**QUEUE,"release":"GO"})

    def test_unsafe_path_denied(self):
        with self.assertRaises(ValueError):
            get_plan(["../../main.py"],http_source_present=False,queue=QUEUE)

if __name__=="__main__":
    unittest.main()
