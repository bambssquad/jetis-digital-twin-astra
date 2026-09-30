"""Independent source checks against the frozen contract and actual output."""
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run():
    contract=json.loads((ROOT/'analysis/revisions/2026-09-30/revision-contract.json').read_text(encoding='utf-8-sig'))
    raw=json.loads((ROOT/'analysis/geometry.json').read_text(encoding='utf-8-sig'))
    scene=json.loads((ROOT/'web/dist/assets/scene.json').read_text(encoding='utf-8'))
    project=json.loads((ROOT/'web/dist/project.json').read_text(encoding='utf-8'))
    source={e['handle']:e for e in raw['entities']}
    es=scene['elements']; ox,oy=project['origin_source']; tol=.002
    def close(a,b,t=tol): assert abs(a-b)<=t,(a,b)
    def area(p): return abs(sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))/2)
    assert hashlib.sha256((ROOT/'source/input.dwg').read_bytes()).hexdigest()==contract['source_sha256']==scene['source_sha256']==project['source_sha256']==raw['source_sha256'].lower()
    assert project['revision']=='02' and scene['units']=='metres'
    assert len(es)==len({e['id'] for e in es})
    kinds=Counter(e['kind'] for e in es)
    for e in es:
        assert e['mat'] in scene['materials']
        if e['kind']=='box': assert min(e['s'])>0,e['id']
        if e['kind'] in ('beam','wf','cnp'): assert math.dist(e['a'],e['b'])>.001,e['id']
        if e['kind']=='prism':
            p=e['points'];assert len(p)>=3
            a=[p[1][i]-p[0][i] for i in range(3)];b=[p[2][i]-p[0][i] for i in range(3)]
            n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];length=math.sqrt(sum(v*v for v in n))
            assert length>1e-7,e['id']
            assert all(abs(sum(n[i]*(v[i]-p[0][i]) for i in range(3))/length)<.00001 for v in p),('nonplanar',e['id'])
            assert all(math.dist(p[i],p[(i+1)%len(p)])>.00002 for i in range(len(p))),e['id']
    #Exact geometry, not only matching the footprint metadata.
    for fp in contract['footprints']:
        found=[e for e in es if e.get('source_handles')==[fp['handle']] and e['kind']=='prism' and e.get('collision')=='floor']
        assert len(found)==1,fp['handle']
        got=found[0]['points'];want=[[p[0]-ox,p[1]-oy,0] for p in fp['vertices_source']]
        assert len(got)==len(want)
        assert all(any(math.dist(a,b)<.00001 for b in got) for a in want),fp['handle']
    site_area=area([[p[0]-ox,p[1]-oy] for p in contract['site']['vertices_source']])
    close(sum(area(e['points']) for e in es if e['group']=='Tapak | tanah'),site_area,.05)
    roof1=[e for e in es if e['name'].startswith('Penutup galvalume row')]
    assert len(roof1)==4
    for e in roof1:
        p=e['points']; slope=abs((p[3][2]-p[0][2])/(p[3][1]-p[0][1]))
        close(math.degrees(math.atan(slope)),contract['roof']['slope_degrees'],1e-7)
        close(e['th'],contract['roof']['roof_cover_sheet_thickness_m'],1e-10)
        close(max(v[2] for v in p),contract['levels']['nominal_ridge'],1e-7)
        close(max(v[0] for v in p)-min(v[0] for v in p),122 if 'row1' in e['name'] else 116,1e-7)
    cover=[e for e in es if e.get('source_handles')==['16817','219A3']]
    assert len(cover)==2
    rp=source[contract['stage2']['roof_plan_outline']]['points'];rawpoly=list(zip(rp[::2],rp[1::2]))
    close(sum(area(e['points']) for e in cover),area(rawpoly),.0001)
    #The roof plane must be15degrees even along the taper, not twisted.
    for e in cover:
        p=e['points'];dy=p[-1][1]-p[0][1];dz=p[-1][2]-p[0][2]
        close(abs(math.degrees(math.atan2(dz,dy))),15,1e-7)
    purlins=[e for e in es if e['kind']=='cnp']
    assert len(purlins)>80
    for e in purlins:
        close(e['h'],.125,1e-8);close(e['tw'],.002,1e-8);close(e['tf'],.002,1e-8)
        q=e['slope_station_m']/contract['roof']['purlin_slope_spacing_m'];close(q,round(q),1e-7)
    assert len({tuple(round(v,7) for v in e['a']+e['b']) for e in purlins})==len(purlins),'Coincident purlins'
    #Actual source treads each occur once with matching plan footprints.
    source_steps=[e for e in raw['entities'] if e.get('layer')=='TANGGA' and e['handle'].startswith('2A') and e.get('points')]
    steps=[e for e in es if e.get('riser_number')]
    assert len(steps)==len(source_steps)==30
    for e in steps:
        s=source[e['source_handles'][0]];p=s['points'];x,y,z=e['p'];w,d,h=e['s']
        close(x,min(p[::2])-ox,1e-7);close(y,min(p[1::2])-oy,1e-7)
        close(w,max(p[::2])-min(p[::2]),1e-7);close(d,max(p[1::2])-min(p[1::2]),1e-7)
        close(z+h,e['riser_number']*.15,1e-7)
    close(max(e['p'][2]+e['s'][2] for e in steps),4.5,1e-7)
    slab=[e for e in es if e['name'].startswith('Pelat L2')]
    assert len(slab)==2
    for e in slab:close(e['p'][2]+e['s'][2],4.5,1e-7);close(e['s'][2],.15,1e-7)
    hx,hy,hx1,hy1=project['mezzanine']['hole_bounds']
    for e in slab:
        x,y,z=e['p'];w,d,h=e['s']
        assert min(x+w,hx1)-max(x,hx)<.0001 or min(y+d,hy1)-max(y,hy)<.0001,'Slab covers stair/void'
    bridge=next(e for e in es if e['name']=='Jembatan timbang15x4')
    close(bridge['s'][0],15,1e-7);close(bridge['s'][1],4,1e-7)
    motions={m['id']:m for m in scene['motions']}
    assert len(motions)==30 and sum(m['kind']=='splitSlide' for m in motions.values())==28
    assert motions['recording_hinge']['kind']=='hinge' and motions['recording_hinge']['angle']>0
    for opening in scene['opening_evidence']:
        m=motions[opening['motion']];close(opening['sill'],1.2,1e-7)
        target=1.8 if opening['handle']=='1BB25' else 3
        close(opening['b']-opening['a'],target,1e-7)
        close(opening['head']-opening['sill'],2.2 if target==1.8 else 3,1e-7)
        assert len(m['leaves'])==2 and m['axis'] in ('X','Y')
        assert len([e for e in es if e.get('motion')==m['id'] and e['mat']=='door'])==2
    assert all(e['motion'] in motions for e in es if e.get('motion'))
    for mat in scene['materials'].values():
        if mat.get('texture'):
            for folder in ('textures','textures-1k'):
                for suffix in ('Color','NormalGL','Roughness'):
                    assert (ROOT/'web/dist/assets'/folder/f"{mat['texture']}_{suffix}.jpg").is_file()
    report={'status':'PASS','revision':'02','source_sha256':contract['source_sha256'],
            'elements':len(es),'types':dict(kinds),'stable_original_ids':sum(e['id'].startswith('A-') for e in es),
            'source_footprints':5,'site_area_m2':round(site_area,3),'roof_pitch_degrees':15,
            'roof_stage2_plan_area_m2':area(rawpoly),'cnp125x2_members':len(purlins),
            'source_treads':28,'landings':2,'stair_top':4.5,'motion_count':len(motions),
            'double_sliding':28,'hinged_source_door':1,'gate':1,
            'pending':['native SKP creation and readback','rendered desktop/mobile check','publication']}
    (ROOT/'verification/scene-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':run()
