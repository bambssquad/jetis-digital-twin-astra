"""Compare saved CAD evidence and index source drawings without mutating CAD."""
import argparse, collections, json, math, re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--new', type=Path, required=True)
p.add_argument('--old', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
new = json.loads(a.new.read_text(encoding='utf-8-sig'))
old = json.loads(a.old.read_text(encoding='utf-8-sig'))
a.out.mkdir(parents=True, exist_ok=True)

def norm(v):
    if isinstance(v, float): return round(v, 6)
    if isinstance(v, list): return [norm(x) for x in v]
    if isinstance(v, dict): return {k:norm(x) for k,x in v.items()}
    return v

before = {e['handle']:e for e in old['entities']}
after = {e['handle']:e for e in new['entities']}
changed = [h for h in after.keys() & before.keys() if norm(after[h]) != norm(before[h])]
added = sorted(after.keys() - before.keys())
removed = sorted(before.keys() - after.keys())
texts = [e for e in new['entities'] if e['type'] in ('AcDbText','AcDbMText')]
titles = []
for e in texts:
    text = str(e.get('text','')).replace('\\P',' / ').replace('\\L','').replace('\\l','')
    text = re.sub(r'\\[A-Za-z][^;]*;', '', text)
    if re.search(r'LAYOUT|DENAH|POTONGAN|TAMPAK|RENC\.|DETAIL|PORTAL',text,re.I):
        titles.append({'handle':e['handle'],'position':e['position'], 'text':text})

outlines = []
for e in new['entities']:
    if e['type'] != 'AcDbPolyline': continue
    v=e.get('points',[])
    if len(v)<6: continue
    xy=list(zip(v[::2],v[1::2])); xs,ys=zip(*xy)
    w,d=max(xs)-min(xs),max(ys)-min(ys)
    if min(w,d)>10 and (e.get('closed') or math.dist(xy[0],xy[-1])<.001):
        area=abs(sum(xy[i][0]*xy[(i+1)%len(xy)][1]-xy[(i+1)%len(xy)][0]*xy[i][1] for i in range(len(xy)))/2)
        outlines.append({'handle':e['handle'],'layer':e['layer'],'bounds':[min(xs),min(ys),max(xs),max(ys)],'size':[w,d],'area':area,'vertices':len(xy)})

summary = {'source_sha256':new['source_sha256'], 'previous_sha256':old['source_sha256'],
           'modelspace_entities':len(new['entities']), 'blocks':len(new['blocks']),
           'insunits':new['insunits'], 'types':dict(collections.Counter(e['type'] for e in new['entities'])),
           'warnings':len(new['warnings']), 'texts':len(texts), 'titles':titles,
           'changed_entities':len(changed), 'added_entities':len(added),'removed_entities':len(removed),
           'changed_by_type':dict(collections.Counter(after[h]['type'] for h in changed)),
           'outlines':outlines}
(a.out/'source-comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(a.out/'entity-changes.json').write_text(json.dumps({'changed':[{ 'handle':h,'old':before[h],'new':after[h]} for h in changed],'added':added,'removed':removed},ensure_ascii=False),encoding='utf-8')
(a.out/'texts.tsv').write_text('\n'.join(f"{e['handle']}\t{e['position'][0]:.3f}\t{e['position'][1]:.3f}\t{e['text']}" for e in texts),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ('outlines','titles')},ensure_ascii=False))
print('DRAWING TITLES')
for e in titles: print(e['handle'], [round(x,2) for x in e['position'][:2]], e['text'])
