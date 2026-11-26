#!/usr/bin/env python3
"""Nightly backup: read the league from Firestore (public read, no login needed) and
write data/league-export.json in the same format as the site's "Export backup".

The file is only rewritten when the league data actually changed, so git history
holds one version per day of changes. Run by .github/workflows/nightly-backup.yml.
Standard library only.
"""
import json, re, sys, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'league-export.json'
CFG = (ROOT / 'firebase-config.js').read_text(encoding='utf-8')
PROJECT = re.search(r'projectId:\s*"([^"]+)"', CFG).group(1)
KEY = re.search(r'apiKey:\s*"([^"]+)"', CFG).group(1)
BASE = f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents'
COLLS = ['teams', 'games', 'tournaments', 'schedule']
FORMAT = ("Knee Hockey League backup v3 — same shape as the app's localStorage key 'kh-locos-v3' (S object). "
          "Firestore: teams/{id}, games/{id}, tournaments/{id}, schedule/{id}, meta/league = {name, seasons, cur}.")


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'knee-hockey-backup'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def plain(v):
    """Firestore REST typed value -> plain JSON value."""
    if 'stringValue' in v: return v['stringValue']
    if 'integerValue' in v: return int(v['integerValue'])
    if 'doubleValue' in v:
        d = float(v['doubleValue'])
        return int(d) if d.is_integer() else d
    if 'booleanValue' in v: return v['booleanValue']
    if 'nullValue' in v: return None
    if 'timestampValue' in v: return v['timestampValue']
    if 'mapValue' in v: return {k: plain(x) for k, x in v['mapValue'].get('fields', {}).items()}
    if 'arrayValue' in v: return [plain(x) for x in v['arrayValue'].get('values', [])]
    raise ValueError(f'unsupported Firestore value: {v}')


def tidy(v):
    """Stable key order (id first, then A-Z) so nightly diffs only show real changes."""
    if isinstance(v, dict):
        return {k: tidy(v[k]) for k in sorted(v, key=lambda k: (k != 'id', k))}
    if isinstance(v, list):
        return [tidy(x) for x in v]
    return v


def doc_fields(d):
    return tidy({k: plain(x) for k, x in d.get('fields', {}).items()})


def collection(name):
    out, token = [], ''
    while True:
        q = {'pageSize': 300, 'key': KEY}
        if token: q['pageToken'] = token
        page = get(f'{BASE}/{name}?{urllib.parse.urlencode(q)}')
        out += [doc_fields(d) for d in page.get('documents', [])]
        token = page.get('nextPageToken')
        if not token: return out


def main():
    meta = doc_fields(get(f'{BASE}/meta/league?key={KEY}'))
    data = {c: collection(c) for c in COLLS}
    if not meta.get('seasons') or not data['teams']:
        sys.exit('League looks empty — not overwriting the backup.')
    data['games'].sort(key=lambda g: (str(g.get('date', '')), str(g.get('ts', '')), str(g.get('id', ''))))
    for c in ('teams', 'tournaments', 'schedule'):
        data[c].sort(key=lambda x: str(x.get('id', '')))
    new = {'_format': FORMAT, 'exportedAt': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
           'name': meta.get('name', 'Knee Hockey League'), 'cur': meta.get('cur'), 'seasons': meta.get('seasons', []), **data}

    strip = lambda d: {k: v for k, v in d.items() if k not in ('_format', 'exportedAt')}
    old = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else {}
    old.setdefault('schedule', [])
    if strip(old) == strip(new):
        print('No changes since the last backup.')
        return
    OUT.write_text(json.dumps(new, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Backed up {len(data['teams'])} teams, {len(data['games'])} games, "
          f"{len(data['tournaments'])} tournaments, {len(data['schedule'])} scheduled.")


if __name__ == '__main__':
    main()
