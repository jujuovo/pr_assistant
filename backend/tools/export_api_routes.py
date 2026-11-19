"""Export actual Flask routes for the frontend request contract audit (no DB writes)."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def export(output):
    os.environ.setdefault("DATABASE_URL","sqlite://")
    from app import app
    routes=[]
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/api/'):
            continue
        parts=[]
        cursor=0
        for found in re.finditer(r'<(?:(\w+):)?(\w+)>',rule.rule):
            parts.append(re.escape(rule.rule[cursor:found.start()]))
            parts.append(r'[0-9]+' if found[1]=='int' else '.+' if found[1]=='path' else '[^/]+')
            cursor=found.end()
        parts.append(re.escape(rule.rule[cursor:]))
        routes.append({'path':rule.rule,'methods':sorted(set(rule.methods)-{'HEAD','OPTIONS'}),
                       'pattern':'^'+''.join(parts)+'$','endpoint':rule.endpoint})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({'routes':routes},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Exported {len(routes)} API routes to {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'outputs'/'integration-api-routes.json')
    export(parser.parse_args().output)
