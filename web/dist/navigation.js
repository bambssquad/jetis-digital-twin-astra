// Collision math shared by the interactive viewer and offline boundary tests.
export const AVATAR_HEIGHT=1.70;
export function overlaps(x,z,r,b,feet,height=AVATAR_HEIGHT+.02){
 return feet+height>b.minY+.01&&feet+.23<b.maxY&&x+r>b.minX&&x-r<b.maxX&&z+r>b.minZ&&z-r<b.maxZ;
}
export function collisionData(data){
 const walls=[],floors=[];
 for(const e of data.elements){
  if(e.motion||e.collision==='none')continue;
  if(e.kind==='box'){
   const [x,y,z]=e.p,[w,d,h]=e.s,b={minX:x,maxX:x+w,minY:z,maxY:z+h,minZ:-y-d,maxZ:-y,name:e.name,group:e.group};
   if(e.collision==='floor'||/^(Lantai |Pelat kantor|Anak tangga kantor|Landing kantor|Pelataran beton|Jalan depan)/.test(e.name))floors.push(b);
   else if(h>=.26&&w>=.03&&d>=.03)walls.push(b);
  }else if(e.kind==='cylinder'&&e.r>=.065&&e.h>=.3){const [x,y,z]=e.p;walls.push({minX:x-e.r,maxX:x+e.r,minZ:-y-e.r,maxZ:-y+e.r,minY:z,maxY:z+e.h,name:e.name});}
  else if(e.kind==='wf'&&Math.abs(e.a[0]-e.b[0])<.01&&Math.abs(e.a[1]-e.b[1])<.01){const[x,y,z]=e.a;walls.push({minX:x-.09,maxX:x+.09,minZ:-y-.09,maxZ:-y+.09,minY:z,maxY:e.b[2],name:e.name});}
 }
 return {walls,floors};
}
export function motionBox(m,p){const[x,y,z,w,d,h]=m.bounds;const dx=m.kind==='slide'?m.delta[0]*p:0,dz=m.kind==='slide'?-m.delta[1]*p:0,up=m.kind==='roll'?m.travel*p:0;
 return {minX:x+dx,maxX:x+w+dx,minZ:-y-d+dz,maxZ:-y+dz,minY:z+up,maxY:m.kind==='roll'?Math.max(z+up,z+h):z+h,name:m.label};}
export function motionBoxes(m,p){return m.kind==='splitSlide'?m.leaves.map((bounds,i)=>motionBox({...m,kind:'slide',bounds,delta:[(i===0?-1:1)*m.travel,0,0]},p)):[motionBox(m,p)];}
export function floorAt(x,z,current,floors,ground=0){let h=ground;for(const b of floors)if(x>=b.minX&&x<=b.maxX&&z>=b.minZ&&z<=b.maxZ&&b.maxY<=current+.24)h=Math.max(h,b.maxY);return h;}
export function moveBody(pos,dx,dz,walls,floors,r=.29,bounds=[-Infinity,Infinity,-Infinity,Infinity],ground=0){
 const n=Math.max(1,Math.ceil(Math.hypot(dx,dz)/.08));let collided=false;
 for(let i=0;i<n;i++){
  for(const axis of ['x','z']){const x=pos.x+(axis==='x'?dx/n:0),z=pos.z+(axis==='z'?dz/n:0),foot=floorAt(x,z,pos.y,floors,ground);
   if(x-r<bounds[0]||x+r>bounds[1]||-z-r<bounds[2]||-z+r>bounds[3]||walls.some(b=>overlaps(x,z,r,b,foot))){collided=true;continue;}
   pos.x=x;pos.z=z;pos.y=foot;
  }
 }
 return collided;
}
export function segmentHit(a,b,box){let lo=0,hi=1;for(const k of ['X','Y','Z']){const key=k.toLowerCase(),d=b[key]-a[key],min=box['min'+k]-.08,max=box['max'+k]+.08;if(Math.abs(d)<1e-7){if(a[key]<min||a[key]>max)return 1;continue;}let t0=(min-a[key])/d,t1=(max-a[key])/d;if(t0>t1)[t0,t1]=[t1,t0];lo=Math.max(lo,t0);hi=Math.min(hi,t1);if(lo>hi)return 1;}return lo>0?lo:1;}
