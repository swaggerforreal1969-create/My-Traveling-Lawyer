"""No-network, read-only mobile HTML view for an authorized MatterBrief snapshot.

Only consume data obtained via MatterBrief.prepare(token, matter_id). The renderer is
not an authentication boundary: callers must authorize the source snapshot first.
Nothing here computes a legal deadline or validates legal authority.
"""
from html import escape

class InvalidBrief(ValueError):
    pass


def _text(value, limit=1600):
    if not isinstance(value, str) or len(value) > limit:
        raise InvalidBrief('Invalid or oversized text field')
    return escape(value, quote=True)


def _items(data, key):
    value = data.get(key)
    if not isinstance(value, list) or len(value) > 100:
        raise InvalidBrief('Invalid or oversized collection: ' + key)
    return value


def _risk_list(brief):
    risks = _items(brief, 'risk_notices')
    return ''.join('<li>' + _text(x, 1000) + '</li>' for x in risks)


def render_mobile_brief(brief):
    """Render an explicitly offline, script-free mobile brief with a privacy cover.

    Fails closed unless the data has the exact read-only MatterBrief v1 schema and
    explicit FALSE indicators for legal verification and outbound AI disclosure.
    All source URLs are displayed as inert text, never linked or fetched.
    """
    if not isinstance(brief, dict) or brief.get('schema') != 'mtl.matter.preparation.v1':
        raise InvalidBrief('Unrecognized matter briefing')
    for flag in ('legal_deadlines_verified', 'legal_authorities_verified_by_software',
                 'outbound_ai_transmission'):
        if brief.get(flag) is not False:
            raise InvalidBrief('Cannot imply verification or external transmission')
    if not isinstance(brief.get('matter_version'), int) or isinstance(brief.get('matter_version'), bool):
        raise InvalidBrief('Invalid matter version')
    matter_title = _text(brief.get('matter_title'), 180)
    matter_id = _text(brief.get('matter_id'), 64)
    at = _text(brief.get('as_of'), 70)
    notes, tasks, sources = (_items(brief, key) for key in ('notes', 'open_tasks', 'research_sources'))
    note_html = []
    for item in notes:
        if not isinstance(item, dict):
            raise InvalidBrief('Invalid note')
        note_html.append('<li>' + _text(item.get('text')) + '</li>')
    task_html = []
    for item in tasks:
        if not isinstance(item, dict) or not isinstance(item.get('past_user_entered_due_time'), bool):
            raise InvalidBrief('Invalid task')
        label = 'Past user-entered date' if item['past_user_entered_due_time'] else 'User-entered date'
        task_html.append('<li>' + _text(item.get('text')) + '<span class="meta">' +
                         _text(label) + ': ' + _text(item.get('due_at'), 70) + '</span></li>')
    source_html = []
    known = {'not_reviewed', 'checked_against_original', 'needs_recheck', 'rejected'}
    for item in sources:
        if not isinstance(item, dict) or item.get('software_verified') is not False:
            raise InvalidBrief('Source cannot be marked software verified')
        status = item.get('last_human_assessment')
        if status not in known:
            raise InvalidBrief('Invalid human review status')
        # No href attributes; source URLs remain inert text to prevent navigation.
        source_html.append('<li>' + _text(item.get('title'), 300) +
                           '<span class="meta">Human review: ' + _text(status, 50) +
                           ' | Source (not authenticated): ' + _text(item.get('url'), 1000) +
                           '</span></li>')
    risks = _risk_list(brief)
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; script-src 'none'; base-uri 'none'; form-action 'none'">
<title>Private Matter Preparation</title>
<style>
:root{color-scheme:light dark;font-family:system-ui,-apple-system,sans-serif}
body{max-width:42rem;margin:auto;padding:1rem;line-height:1.5}
h1{font-size:1.4rem}h2{font-size:1.05rem}section{border:1px solid #8888;border-radius:.7rem;padding:.8rem;margin:.8rem 0}
.meta{display:block;font-size:.8rem;opacity:.82;overflow-wrap:anywhere}
li{margin:.65rem 0;overflow-wrap:anywhere}summary{cursor:pointer;padding:.5rem;font-weight:700}
header{margin-bottom:1rem}.notice{font-weight:700}
</style></head><body><header><h1>Private Matter Preparation</h1>
<p class="notice">LOCAL VIEW ONLY — NOT LEGAL ADVICE. No automatic court-deadline or authority verification.</p>
</header>
<section><details><summary>Reveal matter details (private)</summary><p>''' + matter_title + '''</p><p class="meta">Generated: ''' + at + ''' | Matter: ''' + matter_id + '''</p></details></section>
<section><details><summary>Reveal attention notices</summary><ul>''' + risks + '''</ul></details></section>
<section><details><summary>Reveal notes (''' + str(len(notes)) + ''')</summary><ul>''' + ''.join(note_html) + '''</ul></details></section>
<section><details><summary>Reveal open tasks (''' + str(len(tasks)) + ''')</summary><ul>''' + ''.join(task_html) + '''</ul></details></section>
<section><details><summary>Reveal research sources (''' + str(len(sources)) + ''')</summary><ul>''' + ''.join(source_html) + '''</ul></details></section>
<footer><p class="meta">Human review assertions only. Verify original sources, jurisdiction and currency independently. Do not distribute this file.</p></footer>
</body></html>'''
