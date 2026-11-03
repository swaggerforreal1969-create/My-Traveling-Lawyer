"""Real same-source Chromium acceptance with fictional data; run explicitly."""
import tempfile
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from src.secure_engine import SecureCore
from src.readiness_loopback_http import LoopbackReadinessServer


def main():
    with tempfile.TemporaryDirectory() as td:
        core=SecureCore(Path(td)/'fictional.sqlite3')
        firm=core.provision_firm('Invented Attorney Group')
        _,token=core.provision_user(firm,'Invented Lawyer')
        mid=core.create_matter(token,'PRIVATE CASE TITLE')['id']
        core.add_note(token,mid,'PRIVATE CONFIDENTIAL NOTE')
        server=LoopbackReadinessServer(core)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_address[1]}/v1/matters/{mid}/readiness'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                context=browser.new_context(viewport={'width':390,'height':844}, extra_http_headers={
                    'Authorization':'Bearer '+token,'X-Preview-Ticket':server.issue_ticket(token,mid)['ticket']})
                page=context.new_page()
                response=page.goto(url,wait_until='load',timeout=15000)
                assert response.status==200, ('expected 200',response.status)
                assert page.get_by_text('Private matter readiness').is_visible()
                assert page.get_by_text('Open tasks',exact=True).is_visible()
                assert not page.get_by_text('Independent human review required').is_visible()
                page.get_by_text('Expand procedural breakdown').click()
                assert page.get_by_text('Independent human review required').is_visible()
                assert 'no-store' in response.headers.get('cache-control','')
                html=page.content()
                assert 'PRIVATE CASE TITLE' not in html and 'PRIVATE CONFIDENTIAL NOTE' not in html
                assert page.locator('script,form,img,a').count()==0
                # Browser reload attempts the same ticket and must fail closed.
                replay=page.reload(wait_until='load')
                assert replay.status==403, ('replay',replay.status)
                context.close()
                wrong=browser.new_context(viewport={'width':390,'height':844},extra_http_headers={
                    'Authorization':'Bearer '+token,'X-Preview-Ticket':server.issue_ticket(token,mid)['ticket']})
                other=wrong.new_page()
                denied=other.goto(f'http://127.0.0.1:{server.server_address[1]}/v1/matters/other-matter/readiness')
                assert denied.status==403
                wrong.close();browser.close()
                print('CHROMIUM PASS: 200 verified rendered view, mobile viewport, collapsed review, expand, no secrets, no scripts, 403 replay, 403 wrong matter')
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3);core.close()
if __name__=='__main__':main()
