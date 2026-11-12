import unittest
from tools.windows_error_classifier import classify
class Classification(unittest.TestCase):
    def test_koontcee_event_is_not_mtl(self):
        self.assertEqual(classify("0xc0e90002",3077,False)["verdict"],"UNRESOLVED")
    def test_matching_policy_denial(self):
        self.assertEqual(classify("0xc0e90002",3077,True)["verdict"],"VERIFIED_POLICY_BLOCK")
    def test_missing_dll(self):
        self.assertEqual(classify("0xc0000135",1000,True)["verdict"],"REQUIRES_INVESTIGATION")
    def test_unknown(self):
        self.assertEqual(classify(None,None,False)["verdict"],"UNRESOLVED")
