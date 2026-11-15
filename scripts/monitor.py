"""Public-index discovery monitor. All extracted items are unverified candidates."""
import argparse
import csv
import hashlib
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]

def canonical(url):
    p = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k not in ('fbclid', 'gclid')]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/') or '/', urlencode(sorted(query)), ''))

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.href = None; self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip += 1
        if tag == 'a' and not self.skip:
            self.href = dict(attrs).get('href'); self.parts = []
    def handle_data(self, data):
        if self.href is not None and not self.skip: self.parts.append(data)
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip = max(0, self.skip-1)
        if tag == 'a' and self.href is not None:
            self.links.append((self.href, ' '.join(' '.join(self.parts).split())))
            self.href = None; self.parts = []

def extract(document, source_url, keywords):
    parser = Links(); parser.feed(document); found = {}
    host = urlsplit(source_url).netloc.lower().removeprefix('www.')
    for href, title in parser.links:
        url = canonical(urljoin(source_url, href))
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or parts.netloc.lower().removeprefix('www.') != host: continue
        if len(title) < 24 or not any(k.casefold() in title.casefold() for k in keywords): continue
        found[url] = title
    return found

def update_source(state, source, found, now):
    key = source['url']; baseline = key not in state['sources']; changes = []
    for url, title in sorted(found.items()):
        item_id = hashlib.sha256(url.encode()).hexdigest()[:20]
        old = state['items'].get(item_id)
        changed = old is not None and old['title'] != title
        if not baseline and (old is None or changed):
            changes.append({'kind': 'retitled candidate' if changed else 'newly discovered candidate', 'title': title, 'url': url, 'institution': source['name']})
        state['items'][item_id] = dict(old or {}, id=item_id, title=title, url=url,
            institution=source['name'], first_seen=old['first_seen'] if old else now, last_seen=now,
            verification='unverified title/index match')
    state['sources'][key] = {'last_success': now}
    return baseline, changes

class InstitutionalRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        original = urlsplit(req.full_url).hostname.removeprefix('www.')
        target = urlsplit(newurl)
        if target.scheme != 'https' or (target.hostname or '').removeprefix('www.') != original:
            raise ValueError('redirect outside configured institutional host blocked')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(source):
    try:
        req = Request(source['url'], headers={'User-Agent': 'AfricaPolicyWatch/1.0 (public policy link monitor)', 'Accept': 'text/html'})
        with build_opener(InstitutionalRedirects()).open(req, timeout=20) as response:
            if response.headers.get_content_type() != 'text/html':
                raise ValueError('not an HTML index; configure an HTML source URL')
            raw = response.read(3_000_001)
            if len(raw) > 3_000_000: raise ValueError('index exceeds 3 MB size limit')
            text = raw.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
        if any(t in text.casefold() for t in ('just a moment...', 'verify you are human', 'access denied')):
            raise ValueError('possible access challenge; manual review needed')
        return source, text, None
    except (OSError, ValueError, HTTPError) as error:
        return source, None, f'{type(error).__name__}: {error}'

def atomic(path, content):
    tmp = path.with_suffix(path.suffix + '.tmp'); tmp.write_text(content, encoding='utf-8'); tmp.replace(path)

def load_csv(name):
    with (ROOT/'data'/name).open(newline='', encoding='utf-8') as f: return list(csv.DictReader(f))

def render(state, health):
    esc = lambda s: html.escape(str(s), quote=True)
    items = sorted(state['items'].values(), key=lambda i:i['last_seen'], reverse=True)
    actions = load_csv('actions.csv'); deliverables = load_csv('deliverables.csv')
    def table(rows, fields):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+esc(label)+'</th>' for _,label in fields)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(row.get(key,''))+'</td>' for key,_ in fields)+'</tr>' for row in rows)+'</tbody></table></div>'
    cards = ''.join('<article><small>'+esc(i['institution'])+' · '+esc(i['verification'])+'</small><h3><a target="_blank" rel="noopener" href="'+esc(i['url'])+'">'+esc(i['title'])+'</a></h3><p>First observed '+esc(i['first_seen'])+' · Published date unknown</p></article>' for i in items)
    checked = max((h.get('checked_at','') for h in health),default='Not yet run')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Africa Policy Watch</title><style>
:root{font-family:system-ui,sans-serif;color:#163534;background:#f2f5f0}body{max-width:1180px;margin:auto;padding:32px 22px}header{border-bottom:1px solid #b9cfc5;padding-bottom:22px}small,.muted{color:#476b64}h1{font-size:clamp(32px,5vw,56px);letter-spacing:-2px;margin:10px 0}h2{margin-top:34px}p{line-height:1.6}.pills{display:flex;gap:12px;flex-wrap:wrap}.pill{padding:14px 18px;background:#dceadf;border-radius:10px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;background:white;font-size:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid #e0e8e2;vertical-align:top}th{background:#e0ebe4}article{padding:16px;background:white;border-radius:10px;margin:12px 0}h3{margin:9px 0}a{color:#005f56}input{padding:12px;max-width:95%;width:450px;border:1px solid #a9bfb3;border-radius:7px}.note{border-left:4px solid #c8994f;padding:10px 18px;background:#fff9ed}button{padding:10px 15px;background:#16574b;color:white;border:0;border-radius:6px;cursor:pointer}@media print{button,input{display:none}body{padding:0}.scroll{overflow:visible}}</style>
<header><small>ADAEZE OZOAGU · PERSONAL WORKSPACE</small><h1>Africa Policy Watch</h1><p>Policy intelligence → recommended action → delivery evidence</p><p class="muted">Application preparation · Africa cluster · Provisional role term February 2027–July 2028</p></header>'''
    page += '<p class="muted">Last scanner check: '+esc(checked)+'</p><div class="pills">'+''.join('<div class="pill"><strong>'+str(n)+'</strong> '+label+'</div>' for n,label in [(len(items),'discovery candidates'),(len(actions),'tracked actions'),(len(deliverables),'delivery commitments / habits'),(sum(h.get('status')=='error' for h in health),'source failures')])+'</div>'
    page += '<p class="note">No appointment or completed deliverables are assumed. Index matches are discovery candidates, not verified developments. ChatGPT research and this repository are separate; copy verified actions into your tracker. This dashboard updates when the scanner runs and does not save edits.</p><button onclick="window.print()">Print / save PDF</button>'
    page += '<h2>Next actions</h2>'+table(actions,[('institution','Institution'),('title','Process'),('priority','Priority'),('policy_stage','Stage'),('deadline','Deadline'),('next_action','Next action'),('status','Status')])
    page += '<h2>Delivery evidence</h2>'+table(deliverables,[('id','ID'),('commitment','Commitment'),('basis','Basis'),('due','Due / cadence'),('status','Status'),('evidence','Evidence')])
    page += '<h2>Discovery inbox</h2><input id="filter" aria-label="Filter discovery candidates" placeholder="Filter institution or topic…"><section id="inbox">'+(cards or '<p>No scanner observations yet. Run the workflow to establish a baseline.</p>')+'</section>'
    page += '<h2>Coverage and source health</h2>'+table(health,[('name','Source'),('status','Status'),('matches','Matching links'),('error','Gap / failure')])
    page += '<p class="muted">Edit data/actions.csv and data/deliverables.csv in your private repository, then run the workflow to refresh this view. Unknown deadlines remain unknown until verified.</p><script>document.getElementById("filter").addEventListener("input",function(){const q=this.value.toLowerCase();document.querySelectorAll("#inbox article").forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q))});</script></html>'
    atomic(ROOT/'docs/index.html', page)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--render-only',action='store_true');args=parser.parse_args()
    state=json.loads((ROOT/'data/state.json').read_text());health=json.loads((ROOT/'data/source_health.json').read_text())
    if args.render_only: render(state,health);return 0
    sources=json.loads((ROOT/'config/sources.json').read_text());keywords=json.loads((ROOT/'config/keywords.json').read_text())
    now=datetime.now(timezone.utc).isoformat(timespec='seconds');health=[];changes=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for source, document, error in pool.map(fetch,sources):
            h=dict(name=source['name'],url=source['url'],checked_at=now,status='error' if error else 'ok',error=error or '',matches=0)
            if error is None:
                found=extract(document,source['url'],keywords);h['matches']=len(found)
                baseline,events=update_source(state,source,found,now);h['baseline']=baseline;changes.extend(events)
            health.append(h)
    atomic(ROOT/'data/state.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    atomic(ROOT/'data/source_health.json',json.dumps(health,ensure_ascii=False,indent=2)+'\n')
    errors=[h for h in health if h['status']=='error']
    lines=['# Index discovery scan — '+now,'','Candidates require primary-page verification. Newly discovered does not mean newly published. Retitled does not mean substantively revised.','','## Candidates']
    for event in changes:
        lines.extend(['',f"- {event['institution']} — {event['title']} ({event['kind']})",'  '+event['url']])
    if not changes: lines.append('No new or retitled matching links detected on successfully checked, previously baselined indexes. This does not establish absence of policy developments.')
    lines+=['','## Coverage',f'{len(health)-len(errors)}/{len(health)} sources fetched; {sum(h.get("baseline",False) for h in health)} new baselines.','']
    for h in health: lines.append(f"- {h['name']}: {h['status']}; {h['matches']} matching links. {h['error']}")
    report='\n'.join(lines)+'\n';atomic(ROOT/'briefs/latest.md',report)
    atomic(ROOT/'briefs'/('scan-'+now.replace(':','-')+'.md'),report)
    render(state,health)
    print(f'{len(changes)} discovery candidates; {len(errors)}/{len(health)} source failures')
    return 1 if len(errors)==len(health) else 0

if __name__=='__main__': sys.exit(main())
