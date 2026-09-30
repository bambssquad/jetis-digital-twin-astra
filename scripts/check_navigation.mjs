import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {AVATAR_HEIGHT,collisionData,motionBoxes,overlaps,moveBody,floorAt} from '../web/dist/navigation.js';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const scene=JSON.parse(fs.readFileSync(path.join(root,'web/dist/assets/scene.json'),'utf8'));
const project=JSON.parse(fs.readFileSync(path.join(root,'web/dist/project.json'),'utf8'));
const {walls,floors}=collisionData(scene),bounds=project.walk_bounds;
assert.equal(AVATAR_HEIGHT,1.70);
const failures=[];
function walkRoute(route,reverse=false){
 const points=reverse?[...route.points].reverse():route.points;
 const first=points[0],p={x:first[0],z:-first[1],y:first[2]};
 for(let i=1;i<points.length;i++){
  const q=points[i];moveBody(p,q[0]-p.x,-q[1]-p.z,walls,floors,.29,bounds,0);
  const d=Math.hypot(p.x-q[0],p.z+q[1]);
  if(d>.075||Math.abs(p.y-q[2])>.16){
   const blocks=walls.filter(b=>overlaps(q[0],-q[1],.29,b,floorAt(q[0],-q[1],p.y,floors,0))).map(b=>b.name);
   failures.push({route:route.id,reverse,step:i,distance:d,actual:[p.x,-p.z,p.y],expected:q,blocks:blocks.slice(0,5)});break;
  }
 }
}
for(const route of scene.navigation_routes){walkRoute(route);walkRoute(route,true);}
// A closed opening blocks the avatar and an open one admits it in both axes.
for(const m of scene.motions.filter(m=>m.kind==='splitSlide')){
 const [x,y,z,w,d,h]=m.bounds,cx=x+w/2,cy=y+d/2;
 assert(motionBoxes(m,0).some(b=>overlaps(cx,-cy,.29,b,1.2)),`closed ${m.id}`);
 assert(!motionBoxes(m,1).some(b=>overlaps(cx,-cy,.29,b,1.2)),`open ${m.id}`);
 const p={x:cx+(m.axis==='Y'?-1:0),z:-cy+(m.axis==='X'?1:0),y:1.2};
 const tx=cx+(m.axis==='Y'?1:0),tz=-cy+(m.axis==='X'?-1:0);
 moveBody(p,tx-p.x,tz-p.z,[...walls,...motionBoxes(m,1)],floors,.29,bounds,0);
 if(Math.hypot(p.x-tx,p.z-tz)>.075)failures.push({door:m.id,axis:m.axis,actual:p,target:[tx,tz],blocks:walls.filter(b=>overlaps(cx,-cy,.29,b,1.2)).map(b=>b.name)});
}
// Inward P90 hinge rotates from the west wall into the recording room.
const hinge=scene.motions.find(m=>m.id==='recording_hinge'),[hx,hy,hz,hw,hd]=hinge.bounds;
const hc=[hx+hw/2,hy+hd/2];
assert(motionBoxes(hinge,0).some(b=>overlaps(hc[0],-hc[1],.20,b,0)),'P90 closed collision');
assert(!motionBoxes(hinge,1).some(b=>overlaps(hc[0],-hc[1],.20,b,0)),'P90 open clearance');
const hp={x:hx-.7,z:-hc[1],y:0};moveBody(hp,1.4,0,[...walls,...motionBoxes(hinge,1)],floors,.29,bounds,0);
if(hp.x<hx+.6)failures.push({door:'recording_hinge',actual:hp,blocks:walls.filter(b=>overlaps(hx,-hc[1],.29,b,0)).map(b=>b.name)});
// An upper-floor sample must reach4.5; the stepped void must not act as slab.
const mezz=project.mezzanine,[mx,my]=mezz.bounds;
assert(Math.abs(floorAt(mx+20,-(my+15),4.5,floors)-4.5)<.001);
assert(floorAt(mx+3,-(my+3),4.5,floors)<.01,'void contains no floor2');
const report={status:failures.length?'FAIL':'PASS',avatarHeight:AVATAR_HEIGHT,routes:scene.navigation_routes.length,
 directionChecks:scene.navigation_routes.length*2,doubleDoorChecks:scene.motions.filter(m=>m.kind==='splitSlide').length,
 hingeChecks:1,stairTop:4.5,failures};
fs.writeFileSync(path.join(root,'verification/navigation-audit.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
assert.equal(failures.length,0,'Navigation routes must pass before delivery');
