"""Scoped revision of Astra's original scene using the frozen R02 source contract.

Original site elements and compatible furniture keep their stable IDs. The changed
building envelope, steelwork, source openings and new layout details get AR02 IDs.
All dimensions are metres; one scene drives both SketchUp and Three.js.
"""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'analysis/revisions/2026-09-30/revision-contract.json'
ORIGIN = (2207.9734130790184, 1532.7302629559754)
HANDLE_MAP = {'16551':'2A2B8','165A7':'2A310','165AA':'2A313',
              '1657E':'2A2E5','16582':'2A2E9','1656E':'2A2D5'}


def apply_revision(scene, project, raw):
    contract = json.loads(CONTRACT.read_text(encoding='utf-8-sig'))
    assert raw['source_sha256'].lower() == contract['source_sha256']
    source = {e['handle']: e for e in raw['entities']}
    ox, oy = ORIGIN
    slope = math.tan(math.radians(contract['roof']['slope_degrees']))
    ridge = contract['levels']['nominal_ridge']
    overhang = contract['roof']['upper_cover_overhang_horizontal_m']
    valley_half = contract['roof']['central_valley_gap_m'] / 2
    x0, y0 = 2237.3849435338216-ox, 1556.5475239736475-oy
    xt, yt = 2261.3849435255397-ox, 1636.5475239738967-oy
    elements, motions, routes, opening_evidence = [], [], [], []

    # Retain site, gate and source-compatible low furniture. Remove earlier
    # speculative rooms, tall shelving and equipment obstructing loading paths.
    for e in scene['elements']:
        g, n = e['group'], e['name']
        keep = g.startswith('Tapak |')
        if g.startswith('Interior |') and e.get('kind') == 'box':
            p, size = e['p'], e['s']
            keep = (('Pengolahan utama' in g or 'Ekspansi' in g) and
                    n.startswith(('Conveyor proses','Dudukan conveyor','Meja sortir',
                                  'Kaki meja food-grade','Jalur kemas','Meja kemas','Karton')))
            if keep and 'Pengolahan utama' in g:
                keep = y0+34.8 < p[1] and p[1]+size[1] < y0+54.5
            if keep and 'Ekspansi' in g:
                keep = yt+5 < p[1] and p[1]+size[1] < yt+29
        if keep:
            e = copy.deepcopy(e)
            if e['group'].startswith('Interior |'):
                e['assumption'] = 'Retained visual process fit-out; room function not specified by DWG'
            elements.append(e)
    motions.extend(copy.deepcopy(m) for m in scene['motions'] if m['id'] == 'gate_main')
    seq = 0

    def add(kind, group, name, mat, source_handles=None, **kw):
        nonlocal seq
        seq += 1
        e = dict(id=f'AR02-{seq:05d}', kind=kind, group=group, name=name, mat=mat, **kw)
        if source_handles:
            e['source_handles'] = source_handles if isinstance(source_handles, list) else [source_handles]
        elements.append(e)
        return e

    def box(group, name, mat, p, size, **kw):
        assert min(size) > 0, (name, size)
        return add('box', group, name, mat, p=list(p), s=list(size), **kw)

    def beam(group, name, a, b, w=.05, h=.05, kind='beam', mat='steel', **kw):
        return add(kind, group, name, mat, a=list(a), b=list(b), w=w, h=h,
                   tw=kw.pop('tw', .008), tf=kw.pop('tf', .012), **kw)

    def prism(group, name, mat, pts, th, **kw):
        clean=[]
        for p in pts:
            if not clean or math.dist(p,clean[-1])>1e-8: clean.append(list(p))
        if len(clean)>2 and math.dist(clean[0],clean[-1])<1e-8: clean.pop()
        return add('prism', group, name, mat, points=clean, th=th, **kw)

    def local_poly(handle):
        a = source[handle]['points']
        return [[a[i]-ox, a[i+1]-oy] for i in range(0,len(a),2)]

    def bounds(handle):
        a = local_poly(handle)
        return [min(p[0] for p in a),min(p[1] for p in a),max(p[0] for p in a),max(p[1] for p in a)]

    def floor_rect(group, name, xa, ya, xb, yb, z, th=.15, **kw):
        return box(group,name,'floor',[xa,ya,z-th],[xb-xa,yb-ya,th],collision='floor',**kw)

    # Floors retain exact source polygons, including the non-rectangular stage2.
    for f in contract['footprints']:
        pts = local_poly(f['handle'])
        area = sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))
        if area < 0: pts.reverse()
        prism('Lantai | sumber','Lantai utama ±0 '+f['handle'],'floor',
              [[x,y,0] for x,y in pts],.15,collision='floor',source_handles=f['handle'])

    # Wall openings are formed by real pieces above/below/beside each opening.
    def wall(axis, fixed, start, end, top, openings, name, thickness=.15, base=0, group='Selubung | Tahap 1'):
        cut = sorted({start,end,*[max(start,min(end,o[k])) for o in openings for k in ('a','b')]})
        for j,(a,b) in enumerate(zip(cut,cut[1:])):
            if b-a < 1e-7: continue
            vertical = [(base,top)]
            for o in openings:
                if o['a'] < (a+b)/2 < o['b']:
                    vertical = [(z0,min(z1,o['sill'])) for z0,z1 in vertical if min(z1,o['sill'])>z0] + [(max(base,o['head']),top)]
            for z0,z1 in vertical:
                if z1-z0 < 1e-7: continue
                p=[a,fixed-thickness/2,z0] if axis=='X' else [fixed-thickness/2,a,z0]
                s=[b-a,thickness,z1-z0] if axis=='X' else [thickness,b-a,z1-z0]
                box(group,f'{name} panel {j} {z0:.2f}','wall',p,s,collision='wall')

    def rail(a,b,name,group='Akses | keselamatan'):
        beam(group,name+' atas',[a[0],a[1],a[2]+1.05],[b[0],b[1],b[2]+1.05],.04,.04)
        beam(group,name+' tengah',[a[0],a[1],a[2]+.55],[b[0],b[1],b[2]+.55],.03,.03)
        n=max(1,math.ceil(math.dist(a,b)/1.2))
        for i in range(n+1):
            t=i/n; p=[a[k]+(b[k]-a[k])*t for k in range(3)]
            beam(group,name+' tiang',p,[p[0],p[1],p[2]+1.05],.035,.035)

    def dock(axis,fixed,a,b,key):
        # Approved source-gap resolution: two level platforms and 8 x 150mm
        # steps on both sides connect the +1.20 door sill to floor/yard zero.
        mid=(a+b)/2
        for sign in (-1,1):
            def pt(u,v,z): return [u,fixed+sign*v,z] if axis=='X' else [fixed+sign*v,u,z]
            def rect(u1,u2,v1,v2,z,name):
                p,q=pt(u1,v1,z),pt(u2,v2,z)
                return floor_rect('Akses | dock',name,min(p[0],q[0]),min(p[1],q[1]),max(p[0],q[0]),max(p[1],q[1]),z,max(z,.001),assumption='Approved solid dock/access resolving source sill +1.20 vs floor ±0')
            rect(a-.25,b+.25,.0,1.8,1.2,key+' platform '+str(sign))
            for i in range(8):
                z=1.2-(i+1)*.15
                if z<=0: z=.001
                rect(mid-.6,mid+.6,1.8+i*.30,2.1+i*.30,z,key+f' akses {sign} anak {i+1}')
            for edge in (a-.25,b+.25):
                rail(pt(edge,.15,1.2),pt(edge,1.8,1.2),key+' pagar platform')
            # Route uses actual treads from ground to platform; audit checks
            # both directions and the open/closed animated leaf collision.
            route=[pt(mid,4.25,0)]
            route += [pt(mid,1.95+i*.3,max(.001,1.2-(i+1)*.15)) for i in range(7,-1,-1)]
            route += [pt(mid,1.60,1.2),pt(mid,.30,1.2)]
            routes.append({'id':key+'-dock-'+str(sign),'type':'dock','points':route})

    def double_door(axis,fixed,a,b,handle,label,h=3.0):
        key='door_'+handle.lower(); thickness=.10; sill=1.2
        leaves=[]
        for side in (-1,1):
            u=a if side<0 else (a+b)/2
            p=[u,fixed-thickness/2,sill] if axis=='X' else [fixed-thickness/2,u,sill]
            s=[(b-a)/2,thickness,h] if axis=='X' else [thickness,(b-a)/2,h]
            e=box('Bukaan | Tahap sumber',label+(' kiri' if side<0 else ' kanan'),'door',p,s,
                  motion=key,slideSide=side,source_handles=handle)
            leaves.append(p+s)
            # Door handles follow their leaf using the same axis-aware motion.
            hp=[u+(b-a)/2-.12 if side<0 else u+.08,fixed-.12,sill+1.2] if axis=='X' else [fixed-.12,u+(b-a)/2-.12 if side<0 else u+.08,sill+1.2]
            hs=[.04,.07,.3] if axis=='X' else [.07,.04,.3]
            box('Bukaan | Tahap sumber',label+' pegangan','stainless',hp,hs,motion=key,slideSide=side,collision='none')
        p=[a,fixed-.05,sill] if axis=='X' else [fixed-.05,a,sill]
        size=[b-a,.1,h] if axis=='X' else [.1,b-a,h]
        motions.append(dict(id=key,label=label,kind='splitSlide',axis=axis,travel=(b-a)/2+.08,
                            anchor=[(a+b)/2,fixed] if axis=='X' else [fixed,(a+b)/2],
                            bounds=p+size,leaves=leaves,source_handles=[handle],
                            mechanism_assumption='Industrial split sliding; DWG specifies two leaves only'))
        opening_evidence.append(dict(handle=handle,axis=axis,fixed=fixed,a=a,b=b,sill=sill,head=sill+h,motion=key))
        dock(axis,fixed,a,b,key)
        return dict(a=a,b=b,sill=sill,head=sill+h)

    west=[]
    for h in contract['opening_decision']['stage1_west_handles']:
        p=source[h]['points']; u0=min(p[::2])-3101.3815706733567
        # Source elevations carry a 0.000251 m drafting offset between axes and
        # section dimensions. Map from the actual pedestal centreline.
        u1=max(p[::2])-3101.3815706733567
        west.append(double_door('X',y0+60,x0+114-u1,x0+114-u0,h,'Barat tahap 1 '+str(len(west)+1)))
    east_handles=['21700','21706','2170C','2174D','21753','21759','2179E','217A4','217AA','217B0']
    east=[]
    for h in east_handles:
        p=source[h]['points'];a=min(p[::2])-3246.747947647136;b=max(p[::2])-3246.747947647136
        east.append(double_door('X',y0,x0+a,x0+b,h,'Timur tahap 1 '+str(len(east)+1)))
    south=[]
    # South gable screen u runs east-to-west in source +Y, validated against the
    # two 30 m spans and the east-side module/personnel entrance location.
    south_axis=2904.02611778879
    for h in contract['opening_decision']['stage1_south_handles']:
        p=source[h]['points'];a=min(p[::2])-south_axis;b=max(p[::2])-south_axis
        south.append(double_door('Y',x0,y0+60-b,y0+60-a,h,'Selatan tahap 1 '+str(len(south)+1)))
    #Smaller source personnel double opening at the east end of south elevation.
    personnel_a=2961.7761182947-south_axis; personnel_b=2963.5761182947-south_axis
    south.append(double_door('Y',x0,y0+60-personnel_b,y0+60-personnel_a,'1BB25','Akses personel selatan',h=2.2))
    #Every700x1140mm window frame on this elevation is read from its own
    #polyline, rather than repeating a guessed count or hiding glass in a wall.
    for e in raw['entities']:
        p=e.get('points',[])
        if e.get('type')!='AcDbPolyline' or e.get('layer')!='kusen' or len(p)<6: continue
        a,b,c,d=min(p[::2]),min(p[1::2]),max(p[::2]),max(p[1::2])
        if not (2904<a<2965 and 1664<b<1673 and abs(c-a-.7)<.0001 and abs(d-b-1.14)<.0001): continue
        ya,yb=y0+60-(c-south_axis),y0+60-(a-south_axis)
        sill,head=b-1664.012104314344,d-1664.012104314344
        south.append(dict(a=ya,b=yb,sill=sill,head=head))
        box('Bukaan | Jendela sumber','Jendela sumber '+e['handle'],'glass',[x0-.04,ya,sill],[.08,yb-ya,head-sill],collision='wall',source_handles=e['handle'])
        for yy in (ya,yb-.035):
            box('Bukaan | Jendela sumber','Kusen jendela '+e['handle'],'trim',[x0-.07,yy,sill],[.14,.035,head-sill],collision='none')
    t2_handles=['265F3','26622','26628','2662E','26634','2663A','26640']
    t2doors=[]
    # 84 m east elevation, first door 1.5 m after column axis.
    t2_axis=2972.8215171790634
    for h in t2_handles:
        p=source[h]['points'];a=min(p[::2])-t2_axis;b=max(p[::2])-t2_axis
        t2doors.append(double_door('X',yt,xt+a,xt+b,h,'Timur tahap 2 '+str(len(t2doors)+1)))

    eave=ridge-15*slope
    wall('X',y0,x0,x0+120,eave,east,'Dinding timur')
    wall('X',y0+60,x0,x0+114,eave,west,'Dinding barat')
    # Gable windows shown in the unchanged south elevation. Pair windows in
    # each6 m bay; exact facade-frame heights are source measured below.
    for yi, length in ((y0,120),(y0+30,114)):
        ops=[o for o in south if yi<=o['a']<yi+30]
        wall('Y',x0,yi,yi+30,eave,ops,'Dinding selatan')
        wall('Y',x0+length,yi,yi+30,eave,[],'Dinding utara')
        for xx in (x0,x0+length):
            #Split the triangular gable around the pentagonal vent shown on
            #both ends. South shape is from1BA16/1BA93; north repetition uses
            #the matching elevation motif as a visual detailing assumption.
            left,right=yi+12.45,yi+17.55;vb=10.5387540134;vs=11.1801623258;vt=11.9839618251
            rz=lambda yy:ridge-abs(yy-(yi+15))*slope
            for pts in (
                [[xx,yi,eave],[xx,left,eave],[xx,left,rz(left)]],
                [[xx,right,eave],[xx,yi+30,eave],[xx,right,rz(right)]],
                [[xx,left,eave],[xx,right,eave],[xx,right,vb],[xx,left,vb]],
                [[xx,left,vs],[xx,yi+15,vt],[xx,yi+15,ridge],[xx,left,rz(left)]],
                [[xx,yi+15,vt],[xx,right,vs],[xx,right,rz(right)],[xx,yi+15,ridge]]):
                prism('Selubung | Tahap 1','Panel gevel sekitar ventilasi','wall',pts,.15)
            prism('Bukaan | Ventilasi','Ventilasi gevel5.1m','trim',[[xx-.01,left,vb],[xx-.01,right,vb],[xx-.01,right,vs],[xx-.01,yi+15,vt],[xx-.01,left,vs]],.035,source_handles=['1BA16','1BA93'])
    # The exposed6m return after the upper114m row closes the lower120m row.
    wall('X',y0+30,x0+114,x0+120,eave,[],'Dinding balik 6m')

    # Roofing follows uninterrupted114/120m rows, with a real central valley.
    roof_polygons=[]
    for row,(yi,length) in enumerate(((y0,120),(y0+30,114)),1):
        mid=yi+15
        edges=(yi-overhang if row==1 else yi+valley_half,
               yi+30-valley_half if row==1 else yi+30+overhang)
        for side,(ya,yb) in enumerate(((edges[0],mid),(mid,edges[1]))):
            pts=[[x0-1,ya,ridge-abs(ya-mid)*slope],[x0+length+1,ya,ridge-abs(ya-mid)*slope],
                 [x0+length+1,yb,ridge-abs(yb-mid)*slope],[x0-1,yb,ridge-abs(yb-mid)*slope]]
            e=prism('Atap | Tahap 1',f'Penutup galvalume row{row} sisi{side}','roof',pts,.0004,
                    source_handles=['17468','1746C','1797F'],nominal_sheet_mm=.4)
            roof_polygons.append(e['id'])
        beam('Atap | Tahap 1','Nok menerus',[x0-1,mid,ridge+.025],[x0+length+1,mid,ridge+.025],.18,.05,mat='trim')
        #1.2m distance on roof slope, clipped at edge. Cross section125x50x2.
        for sign in (-1,1):
            k=0 if sign<0 else 1
            while True:
                dist=k*1.2; yy=mid+sign*dist*math.cos(math.radians(15))
                if yy<edges[0]-.001 or yy>edges[1]+.001: break
                z=ridge-dist*math.sin(math.radians(15))-.08
                beam('Struktur | Tahap 1',f'Gording CNP125x50x2 row{row} {sign} {k}',
                     [x0-1,yy,z],[x0+length+1,yy,z],.05,.125,'cnp',tw=.002,tf=.002,
                     source_handles=['17985','1791C'],slope_station_m=dist)
                k+=1
        #Portal every6m. Common columns on the central line are generated once.
        for i in range(int(length/6)+1):
            xx=x0+i*6
            for yy in (yi,yi+30):
                if row==2 and yy==yi and i<=19: continue
                box('Fondasi | Tahap 1','Pedestal 40x60cm','concrete',[xx-.2,yy-.3,-.2],[.4,.6,1.2],source_handles='145A9')
                beam('Struktur | Tahap 1','Kolom WF350',[xx,yy,1],[xx,yy,9],.175,.35,'wf',tw=.007,tf=.011,source_handles='145AE')
            for a,b in ((yi-1,mid),(mid,yi+31)):
                #Source underside profile has ridge13.0192 before nominal shift.
                za=13.0341257188-abs(a-mid)*slope;zb=13.0341257188-abs(b-mid)*slope
                beam('Struktur | Tahap 1','Kuda-kuda WF300',[xx,a,za+.15],[xx,b,zb+.15],.15,.30,'wf',tw=.0065,tf=.009,source_handles='145BA')
        #Ties/bracing remain representative, with source rod nominaldiameters.
        for xx in range(0,int(length),12):
            for edge in edges:
                z=ridge-abs(edge-mid)*slope-.18
                beam('Struktur | Tahap 1','Tali angin Ø16',[x0+xx,edge,z],[x0+xx+6,mid,ridge-.18],.016,.016,source_handles='145C0')
    box('Atap | Talang','Talang lembah menerus','trim',[x0-1,y0+30-valley_half,9.31],[116,valley_half*2,.12])
    for yy,length in ((y0-overhang,120),(y0+60+overhang,114)):
        beam('Atap | Talang','Talang tepi',[x0-1,yy,ridge-(15+overhang)*slope-.06],[x0+length+1,yy,ridge-(15+overhang)*slope-.06],.18,.12,mat='trim')
        for xx in (x0+1,x0+length-1):
            beam('Selubung | Tahap 1','Pipa hujan',[xx,yy,.1],[xx,yy,9.1],.1,.1,mat='trim')
    #Source canopy section17B90 projects4m and drops0.50m. Longitudinal
    #extent follows the door banks; connection details remain representative.
    for a,b,yy,sign in ((x0+36,x0+114,y0+60,1),(x0+36,x0+72,y0,-1),(x0+90,x0+114,y0,-1),(xt,xt+84,yt,-1)):
        pts=[[a,yy,5],[b,yy,5],[b,yy+sign*4,4.5],[a,yy+sign*4,4.5]]
        if sign<0:pts.reverse()
        prism('Atap | Kanopi','Kanopi loading4m','roof',pts,.025,source_handles='17B90',assumption='Door-bank longitudinal extent; representative framing')
        for xx in range(int(round(b-a)/6)+1):
            u=a+6*xx
            beam('Struktur | Kanopi','Konsol kanopi',[u,yy,4.65],[u,yy+sign*4,4.3],.06,.10)

    #Stage2 roof: exact source plan16817 transform, rather than a boundingbox.
    rp=source['16817']['points'];roof2=[[rp[i]-2675.9933620017982+xt,rp[i+1]-1531.408912623925+yt] for i in range(0,len(rp),2)]
    roof2lo=yt-1; roof2ridge=yt+15
    xa,xb=xt-1,xt+85; topa,topb=roof2[0][1],roof2[3][1]
    for pts in (
        [[xa,roof2lo,ridge-16*slope],[xb,roof2lo,ridge-16*slope],[xb,roof2ridge,ridge],[xa,roof2ridge,ridge]],
        [[xa,roof2ridge,ridge],[xb,roof2ridge,ridge],[xb,topb,ridge-(topb-roof2ridge)*slope],[xa,topa,ridge-(topa-roof2ridge)*slope]]):
        prism('Atap | Tahap 2','Atap trapesium sumber16817','roof',pts,.0004,source_handles=['16817','219A3'])
    beam('Atap | Tahap 2','Nok tahap2',[xa,roof2ridge,ridge+.025],[xb,roof2ridge,ridge+.025],.18,.05,mat='trim')
    for sign in (-1,1):
        for k in range(0 if sign<0 else 1,20):
            dist=k*1.2;yy=roof2ridge+sign*dist*math.cos(math.radians(15))
            if yy<roof2lo or yy>topa: continue
            right=xb if yy<=topb else xa+(topa-yy)/(topa-topb)*(xb-xa)
            if right-xa<.1: continue
            beam('Struktur | Tahap 2',f'Gording CNP125x50x2 T2 {sign} {k}',[xa,yy,ridge-dist*math.sin(math.radians(15))-.08],
                 [right,yy,ridge-dist*math.sin(math.radians(15))-.08],.05,.125,'cnp',tw=.002,tf=.002,
                 source_handles=['16817','219A9'],slope_station_m=dist)
    wall('X',yt,xt,xt+84,eave,t2doors,'Dinding timur tahap2',group='Selubung | Tahap 2')
    #Tapered far wall built as coplanar prism, exact36→30m plan edge.
    a,b=[xt,yt+36],[xt+84,yt+30]
    za,zb=ridge-21*slope,ridge-15*slope
    prism('Selubung | Tahap 2','Dinding barat trapesium','wall',[[*a,0],[*b,0],[*b,zb],[*a,za]],.15,collision='wall',source_handles='2A2D5')
    for xx,d in ((xt,36),(xt+84,30)):
        wall('Y',xx,yt,yt+d,min(eave,ridge-(d-15)*slope),[],'Gevel tahap2 dasar',group='Selubung | Tahap 2')
        low=min(eave,ridge-(d-15)*slope)
        prism('Selubung | Tahap 2','Gevel tahap2','wall',[[xx,yt,low],[xx,yt,eave],[xx,yt+15,ridge],[xx,yt+d,ridge-(d-15)*slope]],.15)
    for i in range(15):
        xx=xt+i*6;depth=36-i*6/14
        for yy in sorted(set((yt,yt+30,yt+depth))):
            top=min(9,ridge-abs(yy-roof2ridge)*slope-.4)
            box('Fondasi | Tahap 2','Pedestal T2','concrete',[xx-.2,yy-.3,-.2],[.4,.6,1.2])
            beam('Struktur | Tahap 2','Kolom WF350 T2',[xx,yy,1],[xx,yy,top],.175,.35,'wf',tw=.007,tf=.011)
        for aa,bb in ((yt-1,roof2ridge),(roof2ridge,yt+depth+1)):
            beam('Struktur | Tahap 2','Kuda-kuda WF300 T2',[xx,aa,ridge-abs(aa-roof2ridge)*slope-.30],
                 [xx,bb,ridge-abs(bb-roof2ridge)*slope-.30],.15,.30,'wf',tw=.0065,tf=.009,
                 assumption='Taper extension framing follows15-degree roof; representative connection')

    #Full east120x30m L2 proven by AA17B47 and20 successive CC beam panels.
    #The combined opening for the stepped void plus all drawn treads is a
    #rectangle; the separate void boundary remains stepped in the rail/metadata.
    stair_x0,stair_x1=x0+7-0.175,x0+12-.075
    hole=[x0+.075,y0+.075,x0+11.925,y0+6.075]
    floor_rect('Interior | Lantai dua','Pelat L2 timur120x30 bagianutara',x0+.075,hole[3],x0+120-.075,y0+30-.075,4.5,.15,source_handles=['17B47','1D8DB','2130C'],assumption='Continuous slab infill and150mm slab thickness inferred; drawn300mm is framing depth')
    floor_rect('Interior | Lantai dua','Pelat L2 timur120x30 bagiantimur',hole[2],y0+.075,x0+120-.075,hole[3],4.5,.15,source_handles=['17B47','1D8DB','2130C'],assumption='Continuous slab infill and150mm slab thickness inferred; drawn300mm is framing depth')
    for xx in range(0,121,6):
        #Mezzanine beam stops outside the stair-opening zone.
        ya=hole[3] if xx<12 else y0+.15
        beam('Struktur | Mezzanine','Balok induk WF300 L2',[x0+xx,ya,4.02],[x0+xx,y0+30-.15,4.02],.15,.30,'wf',tw=.0065,tf=.009,source_handles='17B84')
    for yy in range(9,30,3):
        beam('Struktur | Mezzanine','Balok anak WF150 L2',[x0+.15,y0+yy,4.1],[x0+119.85,y0+yy,4.1],.075,.15,'wf',tw=.005,tf=.007,source_handles='17B82')
    #Stair riser assignment follows physical travel order:14 treads,+landing,
    #10 treads,+landing,4 treads;30 rises of150mm reaches exactly+4.50.
    ts=[e for e in raw['entities'] if e.get('layer')=='TANGGA' and e['handle'].startswith('2A') and e.get('points')]
    def tb(e):
        p=e['points'];return [min(p[::2])-ox,min(p[1::2])-oy,max(p[::2])-ox,max(p[1::2])-oy]
    first=sorted([e for e in ts if abs((tb(e)[2]-tb(e)[0])-.3)<.001],key=lambda e:tb(e)[0])
    other=sorted([e for e in ts if e not in first],key=lambda e:tb(e)[1])
    stair_order=first+other
    stair_route=[[tb(first[0])[0]-.25,(tb(first[0])[1]+tb(first[0])[3])/2,0]]
    for i,e in enumerate(stair_order,1):
        a,b,c,d=tb(e);z=i*.15
        floor_rect('Interior | Tangga sumber',f'Tangga sumber {i:02d}',a,b,c,d,z,.12,source_handles=e['handle'],riser_number=i)
        stair_route.append([(a+c)/2,(b+d)/2,z])
    stair_route.append([x0+11.475,y0+6.30,4.5])
    routes.append({'id':'stair-source-30-rises','type':'source_stair','points':stair_route})
    #Two stringers carry each flight. Landing legs sit at the outside corners,
    #clear of the .90m walking route. Their profiles are visual assumptions.
    for ya in (y0+.13,y0+.92):
        beam('Struktur | Tangga','Stringer tangga pertama',[x0+6.825,ya,-.03],[x0+11.025,ya,2.07],.05,.10)
    for xx in (x0+11.08,x0+11.87):
        beam('Struktur | Tangga','Stringer tangga kedua',[xx,y0+.975,2.13],[xx,y0+3.975,3.63],.05,.10)
        beam('Struktur | Tangga','Stringer tangga akhir',[xx,y0+4.875,3.87],[xx,y0+6.075,4.47],.05,.10)
    for ly,lz in ((y0+.075,2.25),(y0+3.975,3.90)):
        for xx in (x0+11.075,x0+11.875):
            for yy in (ly+.05,ly+.85):
                beam('Struktur | Tangga','Kaki landing',[xx,yy,0],[xx,yy,lz-.12],.05,.05)
    #Stepped void guard follows actual2A453 railing, preserving the first
    #flight's lower edge rather than fencing across its entry.
    voidpoly=[[x0+.075,y0+.075],[x0+6.675,y0+.075],[x0+6.675,y0+.975],
              [x0+11.025,y0+.975],[x0+11.025,y0+5.925],[x0+.075,y0+5.925]]
    rail([x0+.15,y0+6.075,4.5],[x0+11.0,y0+6.075,4.5],'Pagar void sumber')
    #Stair handrail heights follow the treads and keep .90m clear walking width.
    rail([x0+6.825,y0+.095,.15],[x0+11.025,y0+.095,2.10],'Pegangan tangga pertama')
    rail([x0+11.905,y0+.975,2.25],[x0+11.905,y0+3.975,3.75],'Pegangan tangga kedua')
    rail([x0+11.905,y0+4.875,3.9],[x0+11.905,y0+6.075,4.5],'Pegangan tangga akhir')
    wall('Y',x0+12,y0,y0+12,4.2,[dict(a=y0+7,b=y0+8.2,sill=0,head=2.4)],'Partisi modul12m',group='Interior | Modul12m')
    wall('X',y0+12,x0,x0+12,4.2,[dict(a=x0+5,b=x0+6.2,sill=0,head=2.4)],'Partisi modul12m',group='Interior | Modul12m')

    #New15x4 weighbridge with shallow deck flush enough for character access.
    wx,wy,wx1,wy1=bounds('2A318')
    floor_rect('Tapak | Timbangan','Jembatan timbang15x4',wx,wy,wx1,wy1,.15,.30,source_handles='2A318')
    for k in range(15):
        box('Tapak | Timbangan','Sambungan dek timbangan','trim',[wx+k,wy,.151],[.025,4,.008],collision='none')
    floor_rect('Tapak | Timbangan','Pelat akses timbangan barat',wx-.6,wy,wx,wy1,.075,.15,assumption='Approach height inferred')
    floor_rect('Tapak | Timbangan','Pelat akses timbangan timur',wx1,wy,wx1+.6,wy1,.075,.15,assumption='Approach height inferred')
    #Recordingroom: source3m centreline walls, west inward hinge0.82clear.
    rx,ry=2253.884943188941-ox,1553.5475239736475-oy
    ra,rb=1555.612523973647-oy,1556.4325239736468-oy
    win_a,win_b=2254.6349435100037-ox,2256.1349428678786-ox
    floor_rect('Interior | Pencatatan','Lantai pencatatan',rx-.075,ry-.075,rx+3.075,ry+3.075,0,.15,source_handles='2A425')
    wall('Y',rx,ry,ry+3,3.0,[dict(a=ra,b=rb,sill=0,head=2.1)],'Pencatatan barat',group='Interior | Pencatatan')
    wall('Y',rx+3,ry,ry+3,3.0,[],'Pencatatan timur',group='Interior | Pencatatan')
    wall('X',ry,rx,rx+3,3.0,[dict(a=win_a,b=win_b,sill=.9,head=2.1)],'Pencatatan selatan',group='Interior | Pencatatan')
    wall('X',ry+3,rx,rx+3,3.0,[],'Pencatatan utara',group='Interior | Pencatatan')
    box('Interior | Pencatatan','Jendela aluminium1.5m','glass',[win_a,ry-.025,.9],[win_b-win_a,.05,1.2],collision='wall',source_handles='2A438')
    floor_rect('Atap | Pencatatan','Atap datar ruang pencatatan',rx-.3,ry-.3,rx+3.3,ry+3.3,3.18,.18,assumption='Room height3m and flat roof are visualization assumptions')
    key='recording_hinge';p=[rx-.025,ra,0];size=[.05,rb-ra,2.1]
    box('Bukaan | Pencatatan','P90 pencatatan inward','wood',p,size,motion=key,source_handles='2A431')
    #Hinge at north jamb rotates west-wall leaf inward into +X room.
    motions.append(dict(id=key,label='P90 ruang pencatatan',kind='hinge',pivot=[rx,rb,0],angle=math.pi/2,
                        bounds=p+size,anchor=[rx,(ra+rb)/2],source_handles=['2A431']))
    box('Interior | Pencatatan','Meja pencatatan','wood',[rx+1.4,ry+.35,.75],[1.2,.65,.08])
    box('Interior | Pencatatan','Monitor timbangan','steel',[rx+1.8,ry+.48,.85],[.5,.07,.35])

    #Light fixtures and sparse fit-out sit below the source full mezzanine.
    for xx in range(9,118,12):
        for yy in (8,22):
            box('Interior | Lantai utama','Lampu bawah mezzanine','light',[x0+xx,y0+yy,3.88],[1.2,.15,.06],collision='none')
        for yy in (38,52):
            box('Interior | Proses','Lampu highbay sumber','light',[x0+xx,y0+yy,8.2],[1.2,.15,.06],collision='none')
    for xx in (24,42,60,78,96):
        for yy in (10,19):
            box('Interior | Lantai utama','Rak rendah asumsi','steel',[x0+xx,y0+yy,0],[3,.8,2.6])
            for z in (.5,1.3,2.1):
                box('Interior | Lantai utama','Produk dingin asumsi','cold',[x0+xx+.15,y0+yy+.12,z],[2.7,.58,.4])

    project=copy.deepcopy(project)
    for f in project['source_footprints']:
        f['handle']=HANDLE_MAP.get(f['handle'],f['handle'])
        f['name']=f['name'].replace('Pengolahan utama','Blok78m').replace('Gudang dingin','Blok84m').replace('Sayap layanan','Bagian36m')
    project.update(source_filename=contract['source_filename'],source_sha256=contract['source_sha256'],
                   revision='02',status='configured',ground_height=0,
                   unit_evidence=['2A31078x30m +label2A2FC','2A31384x30m +label2A2FE','17475/17476 spans30m'],
                   status_detail='DWG revisi 30 September: tapak, potongan, atap 15°, tangga, void dan bukaan; dock serta akses adalah asumsi yang disetujui.',
                   implementation={'variant':'Astra','model':'gpt-6-astra','reasoning_effort':'high','worker':'astra_revision',
                                   'basis':'Requested Astra High subagent runtime; no claim of model switching'},
                   mezzanine={'bounds':[x0,y0,120,30],'top':4.5,'thickness':.15,'hole_bounds':hole,
                              'void_polygon':voidpoly,'source_handles':['17B47','1D8DB','1D76B','2130C']})
    project['roof_groups']=sorted({e['group'] for e in elements if e['group'].startswith('Atap |')})
    project['interior_groups']=sorted({e['group'] for e in elements if e['group'].startswith('Interior |')})
    project['views']['process'].update(title='Lantai utama dan mezzanine',detail='Lantai utama ±0 dan lantai dua +4,50 mengikuti potongan; proses adalah asumsi.',eye=[x0+48,y0+12,2.0],target=[x0+70,y0+17,1.6])
    project['views']['phase2']['detail']='Tapak dan atap trapesium tahap 2 mengikuti poligon DWG, dengan lereng 15°.'
    project['views']['stairs']={'title':'Tangga dan void','detail':'Modul 12 m, 28 anak tangga dan 2 bordes ke +4,50.','eye':[x0+10,y0+10,7.5],'target':[x0+8.5,y0+4.8,2.5]}
    project['views']['weighbridge']={'title':'Jembatan timbang 15 × 4 m','detail':'Ruang pencatatan 3 × 3 m dengan pintu P90 membuka ke dalam.','eye':[wx+16,wy-15,10],'target':[wx+7.5,wy+4,1]}
    project['spawn']=[x0+18,y0-9,0]
    assumptions=[
        'Sumber revisi 30 September 2026; tapak dan lima footprint mengikuti poligon DWG, dalam meter.',
        'Lantai utama ±0, lantai dua +4,50 mengikuti potongan A-A dan C-C; +1,00 adalah kepala pedestal. Pelat lantai dua menerus setebal 150 mm merupakan asumsi dari bentang rangka.',
        'Atap 15° mengikuti profil; nok nominal 13,50 m, penutup galvalume 0,40 mm, CNP 125 × 50 × 2 mm tiap 1,20 m pada lereng.',
        'Bam memilih ambang pintu +1,20 dengan dock dan akses dalam/luar sebagai asumsi realistis. Mekanisme pintu utama dua daun geser adalah asumsi; P90 pencatatan membuka ke dalam sesuai sumber.',
        'Tangga mempertahankan 28 anak tangga 0,30 m dan 2 bordes 0,90 m; 30 kenaikan 150 mm adalah asumsi untuk mencapai +4,50.',
        'Ruang pencatatan 3 × 3 m berdinding 150 mm; tinggi 3 m, atap datar dan ambang jendela 0,90 m adalah asumsi.',
        'Profil WF350, WF300 dan WF150 mengikuti catatan; tebal flange/web, sambungan, fondasi, rangka ekstensi, peralatan proses dan lanskap merupakan visualisasi, bukan desain struktur.',
        'Utara mengikuti +X lokal. Tidak ada georeferensi atau verifikasi kondisi eksisting. Ekstraksi tidak menerjemahkan hatch, ellipse dan point secara semantik.'
    ]
    scene.update(elements=elements,motions=motions,footprints=project['source_footprints'],assumptions=assumptions,
                 revision='02',source_sha256=contract['source_sha256'],navigation_routes=routes,
                 opening_evidence=opening_evidence,roof_outline_stage2=roof2,
                 labels=[{'text':'Jembatan timbang 15 × 4 m','p':[wx+7.5,wy+2,.6]},
                         {'text':'Pencatatan hasil timbangan','p':[rx+1.5,ry,2.6]},
                         {'text':'Lantai dua +4,50','p':[x0+20,y0+15,5.1]},
                         {'text':'Tahap 1 · DWG revisi','p':[x0+75,y0+45,3]},
                         {'text':'Tahap 2 · atap trapesium','p':[xt+42,yt+15,3]}])
    return scene,project
