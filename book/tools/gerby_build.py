#!/usr/bin/env python3
"""Build the prepared manuscript with the real Gerby renderer, importer and web application.

Run with runtime/.venv/bin/python (tools/build.py does). Reads runtime/build/resolution.tex,
references.bib and tags.csv (Gerby's TAG,label register) and writes runtime/gerby/build/.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"


def main():
    source = RUNTIME / "build"
    text = (source / "resolution.tex").read_text()
    entries = []
    for row in (source / "tags.csv").read_text().splitlines():
        if not row or row.startswith('#'):
            continue
        tag, label = row.split(',', 1)
        if not re.fullmatch('[0-9A-Z]{4}', tag):
            raise ValueError('Invalid tag: ' + tag)
        entries.append((tag, label))
    if len(set(t for t, l in entries)) != len(entries):
        raise ValueError('Duplicate tags')
    if len(set(l for t, l in entries)) != len(entries):
        raise ValueError('Duplicate labels')
    actual_labels = set(re.findall(r'\\label\{([^}]+)\}', re.sub(r'(?m)(?<!\\)%.*$', '', text)))
    missing = actual_labels - set(l for t, l in entries)
    if missing:
        raise ValueError('Labels without stable tags: ' + str(sorted(missing)))
    build = RUNTIME / 'gerby/build'
    build.mkdir(parents=True, exist_ok=True)
    for name in ['document', 'document.paux', 'resolution.sqlite', 'comments.sqlite']:
        p = build / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    # Gerby's native theorem/proof nodes carry the tag and proof relationships.
    # plasTeX's generic amsthm adapter flattens them, so use the native nodes for
    # HTML while retaining amsthm in the conventional downloadable LaTeX source.
    (build / 'document.tex').write_text(text.replace('amsmath,amsthm,hyperref', 'amsmath,hyperref'))
    shutil.copy2(source / 'references.bib', build / 'references.bib')
    shutil.copy2(source / 'tags.csv', build / 'tags')
    env = dict(__import__('os').environ, TEXINPUTS='.:')
    subprocess.run([str(RUNTIME / '.venv/bin/plastex'), '--renderer=Gerby', '--imager=none', 'document.tex'],
                   cwd=build, env=env, check=True)
    subprocess.run([sys.executable, str(RUNTIME / 'deps/gerby-website/gerby/tools/update.py')],
                   cwd=RUNTIME, env=env, check=True)
    # Use the actual Flask routes, not a substitute renderer, to validate output.
    from gerby import app
    from gerby.database import Tag, Proof, Dependency
    from gerby.presentation import prepare_presentation
    presentation = prepare_presentation(build)
    routes = ['/', '/browse', '/read', '/bibliography', '/download/manuscript.tex']
    routes += ['/tag/' + tag for tag, label in entries if Tag.select().where(Tag.tag == tag).exists()]
    routes += ['/read/' + tag.tag for tag in Tag.select().where(Tag.type << ['part', 'chapter', 'section', 'subsection'])]
    checks = []
    with app.test_client() as client:
        for route in routes:
            response = client.get(route)
            if response.status_code != 200:
                raise RuntimeError((route, response.status_code))
            checks.append({'route': route, 'status': response.status_code, 'bytes': len(response.data)})
    report = {'tex': str(source / 'resolution.tex'), 'tags': str(source / 'tags.csv'),
              'active_tags': Tag.select().where(Tag.active == True).count(),  # noqa: E712
              'proofs': Proof.select().count(), 'dependencies': Dependency.select().count(),
              'presentation': presentation,
              'checked_routes': checks, 'renderer': 'plasTeX Gerby', 'application': 'gerby-project/gerby-website'}
    (build / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'checked_routes'}, indent=2))


if __name__ == '__main__':
    main()
