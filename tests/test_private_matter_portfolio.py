"""Confidential multi-matter portfolio exercised on real fictional SecureCore."""
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch

from src.secure_engine import SecureCore, Denied, Invalid
from src.private_attorney_operator import PrivateAttorneyOperator
from src.private_matter_portfolio import render_portfolio_plain, PrivateMatterPortfolio


class PrivateMatterPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.core=SecureCore(Path(self.tmp.name)/"fake-attorney-portfolio.sqlite3")
        firm=self.core.provision_firm("Fictional Confidential Office")
        self.owner_id,self.owner=self.core.provision_user(firm,"Fictional Owner")
        self.editor_id,self.editor=self.core.provision_user(firm,"Fictional Editor")
        self.reader_id,self.reader=self.core.provision_user(firm,"Fictional Reader")
        other=self.core.provision_firm("Unrelated Fictional Firm")
        _,self.outsider=self.core.provision_user(other,"Unrelated Outsider")
        self.first=self.core.create_matter(self.owner,"PRIVATE FIRST CASE TITLE")["id"]
        self.second=self.core.create_matter(self.owner,"PRIVATE SECOND CASE TITLE")["id"]
        self.hidden=self.core.create_matter(self.owner,"PRIVATE HIDDEN CASE")["id"]
        for i,mid in enumerate((self.first,self.second)):
            self.core.grant(self.owner,mid,self.editor_id,"editor",10+i)
            self.core.grant(self.owner,mid,self.reader_id,"viewer",20+i)
            self.core.create_task(self.owner,mid,"SECRET PRIVATE TASK "+str(i),
                                  "2026-10-01T00:00:00Z")
        self.operator=PrivateAttorneyOperator(self.core)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def test_editor_two_matter_counts_are_private_and_read_only(self):
        initial=self.core.db.execute("SELECT count(*) FROM audit_chain").fetchone()[0]
        result=self.operator.portfolio(self.editor)
        self.assertEqual(len(result.items),2)
        self.assertEqual(result.total_open_tasks,2)
        self.assertEqual(result.total_second_reviews,0)
        self.assertTrue(all(x.may_act for x in result.items))
        summary=self.operator.portfolio_summary(self.editor)
        self.assertIn("Matters: 2",summary)
        self.assertIn("Open user-entered tasks: 2",summary)
        for secret in ("PRIVATE FIRST","PRIVATE SECOND","PRIVATE HIDDEN",
                       "SECRET PRIVATE TASK",self.first,self.second,
                       self.hidden,self.editor):
            self.assertNotIn(secret,summary)
        self.assertFalse(result.official_law_verified)
        self.assertFalse(result.court_filing_approved)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain").fetchone()[0],initial)

    def test_reader_may_view_counts_without_editor_access(self):
        result=self.operator.portfolio(self.reader)
        self.assertEqual(result.total_open_tasks,2)
        self.assertTrue(all(not item.may_act for item in result.items))
        self.assertEqual(result.total_second_reviews,0)
        self.assertIn("reader",render_portfolio_plain(result))

    def test_outside_firm_and_revoked_user_cannot_infer_matter_count(self):
        result=self.operator.portfolio(self.outsider)
        self.assertEqual(len(result.items),0)
        self.assertEqual(result.total_open_tasks,0)
        self.core.revoke_token(self.editor)
        with self.assertRaises(Denied):
            self.operator.portfolio(self.editor)
        with self.assertRaises(Denied):
            self.operator.portfolio_summary(self.editor)

    def test_changed_matter_index_fails_whole_portfolio(self):
        real=self.operator.matters
        calls=[0]
        def unstable(token):
            calls[0]+=1
            result=real(token)
            if calls[0]>1:
                return dict(result,matters=result["matters"][:-1])
            return result
        with patch.object(self.operator,"matters",side_effect=unstable):
            with self.assertRaises(Denied):
                self.operator.portfolio(self.editor)

    def test_mid_batch_reauthorization_failure_returns_no_partial_result(self):
        real=self.operator.select_matter
        calls=[0]
        def deny_second(*args,**kwargs):
            calls[0]+=1
            if calls[0]==2:raise Denied("Simulated revoked matter")
            return real(*args,**kwargs)
        with patch.object(self.operator,"select_matter",side_effect=deny_second):
            with self.assertRaises(Denied):self.operator.portfolio(self.editor)

    def test_duplicate_and_malformed_matter_index_fail_closed(self):
        index=self.operator.matters(self.editor)
        original=self.operator.matters
        bad=dict(index,matters=[index["matters"][0]]*2)
        with patch.object(self.operator,"matters",return_value=bad):
            with self.assertRaises(Invalid):self.operator.portfolio(self.editor)
        with patch.object(self.operator,"matters",return_value=dict(index,matters=None)):
            with self.assertRaises(Invalid):self.operator.portfolio(self.editor)

    def test_count_forgery_and_privilege_forgery_rejected(self):
        real=self.operator.select_matter
        for field,value in (("open_task_count",True),
                            ("pending_second_review_count",-1),
                            ("court_filing_approved",True),
                            ("external_ai_transmission",True)):
            def fabricated(*args,**kwargs):
                return replace(real(*args,**kwargs),**{field:value})
            with self.subTest(field=field),patch.object(
                    self.operator,"select_matter",side_effect=fabricated):
                with self.assertRaises(Invalid):
                    self.operator.portfolio(self.editor)

    def test_invalid_rendered_totals_and_positions_are_rejected(self):
        snapshot=self.operator.portfolio(self.editor)
        for forged in (
            replace(snapshot,total_open_tasks=100),
            replace(snapshot,total_open_tasks=True),
            replace(snapshot,court_filing_approved=True),
            replace(snapshot,items=(replace(snapshot.items[0],position=4),)+snapshot.items[1:]),
            replace(snapshot,items=(replace(snapshot.items[0],pending_second_reviews=2,
                                           may_act=False),)+snapshot.items[1:])):
            with self.subTest(forged=forged):
                with self.assertRaises(Invalid):render_portfolio_plain(forged)

    def test_real_terminal_portfolio_command_is_read_only(self):
        from src.local_operator_cli import LocalOperatorConsole
        answers=iter(["P","0"])
        output=[]
        LocalOperatorConsole(
            self.core,read=lambda prompt:next(answers),
            write=output.append).run(self.editor)
        rendered="\\n".join(output)
        self.assertIn("PRIVATE ATTORNEY MATTER PORTFOLIO",rendered)
        self.assertIn("Open user-entered tasks: 2",rendered)
        for secret in ("PRIVATE FIRST CASE","PRIVATE SECOND CASE",
                       self.first,self.second,self.editor):
            self.assertNotIn(secret,rendered)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM tasks WHERE completed=1").fetchone()[0],0)

    def test_repeated_reads_do_not_grant_task_write_authority(self):
        snapshot=self.operator.portfolio(self.reader)
        self.assertFalse(snapshot.items[0].may_act)
        matter=self.first
        tasks=self.operator.workflow.journey.workbench.matter(
            self.owner,matter)["open_tasks"]
        with self.assertRaises(Denied):
            self.operator.complete_task(self.reader,matter,
                                        tasks[0]["task_id"],tasks[0]["version"])
        self.assertEqual(self.operator.portfolio(self.reader).total_open_tasks,2)


if __name__=="__main__":
    unittest.main()
