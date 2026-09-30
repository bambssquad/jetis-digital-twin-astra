"""Write/read editable SKP using the installed SketchUp 2023 C API, without MCP.

API references: https://extensions.sketchup.com/developers/sketchup_c_api/sketchup/
All scene coordinates are metres; native C API coordinates are inches.
"""
import argparse, ctypes as C, hashlib, json, math, os
from collections import Counter
from pathlib import Path

R=C.c_void_p; N=C.c_size_t; B=C.c_bool; D=C.c_double; S=C.c_char_p
PR=C.POINTER(R); PN=C.POINTER(N)
INCH=1/0.0254
class Point(C.Structure): _fields_=[('x',D),('y',D),('z',D)]
class UV(C.Structure): _fields_=[('x',D),('y',D)]
class Matrix(C.Structure): _fields_=[('values',D*16)]
class Bounds(C.Structure): _fields_=[('minimum',Point),('maximum',Point)]
class Color(C.Structure): _fields_=[('red',C.c_ubyte),('green',C.c_ubyte),('blue',C.c_ubyte),('alpha',C.c_ubyte)]
class MatInput(C.Structure): _fields_=[('num_uv_coords',N),('uv_coords',UV*4),('vertex_indices',N*4),('material',R)]
def enc(v): return str(v).encode('utf-8')
def vec(a,b):return [a[i]-b[i] for i in range(3)]
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def unit(v):
 n=math.sqrt(sum(x*x for x in v));assert n>1e-10;return [x/n for x in v]
def transform(origin=(0,0,0),axes=None):
 axes=axes or [[1,0,0],[0,1,0],[0,0,1]]
 return Matrix((D*16)(*(sum([a+[0] for a in axes],[])+[x*INCH for x in origin]+[1])))
def world(v,tr):
 t=tr.values;return [(sum(t[k*4+i]*v[k] for k in range(3))+t[12+i])/INCH for i in range(3)]
def extrude(poly,length):
 n=len(poly);v=[[x,y,0] for x,y in poly]+[[x,y,length] for x,y in poly]
 return v,[list(range(n-1,-1,-1)),list(range(n,n*2))]+[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
def mesh(e):
 k=e['kind'];tr=transform(e.get('p',[0,0,0]))
 if k=='box':
  w,d,h=e['s'];v,f=extrude([[0,0],[w,0],[w,d],[0,d]],h)
 elif k in ('beam','wf','cnp'):
  w,h=e['w'],e['h'];z=unit(vec(e['b'],e['a']));length=math.dist(e['a'],e['b'])
  if k=='beam':poly=[[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]]
  elif k=='wf':
   tw,tf=e['tw'],e['tf'];poly=[[-w/2,-h/2],[w/2,-h/2],[w/2,-h/2+tf],[tw/2,-h/2+tf],[tw/2,h/2-tf],[w/2,h/2-tf],[w/2,h/2],[-w/2,h/2],[-w/2,h/2-tf],[-tw/2,h/2-tf],[-tw/2,-h/2+tf],[-w/2,-h/2+tf]]
  else:
   tw,tf=e['tw'],e['tf'];poly=[[-w/2,-h/2],[w/2,-h/2],[w/2,-h/2+tf],[-w/2+tw,-h/2+tf],[-w/2+tw,h/2-tf],[w/2,h/2-tf],[w/2,h/2],[-w/2,h/2]]
  v,f=extrude(poly,length);ref=[0,1,0] if abs(z[2])>.99 else [0,0,1];x=unit(cross(ref,z));y=unit(cross(z,x));tr=transform(e['a'],[x,y,z])
 elif k in ('cylinder','wheel'):
  h=e['d'] if k=='wheel' else e['h'];v,f=extrude([[e['r']*math.cos(i*math.tau/16),e['r']*math.sin(i*math.tau/16)] for i in range(16)],h)
  if k=='wheel':tr=transform([e['p'][0],e['p'][1]+h/2,e['p'][2]],[[1,0,0],[0,0,1],[0,-1,0]])
 elif k=='sphere':
  lat,lon=6,10;s=e['s'];v=[[0,0,s[2]],[0,0,-s[2]]]
  for i in range(1,lat):
   a=math.pi*i/lat
   for j in range(lon):
    b=math.tau*j/lon;v.append([s[0]*math.sin(a)*math.cos(b),s[1]*math.sin(a)*math.sin(b),s[2]*math.cos(a)])
  f=[]
  for j in range(lon):
   q=(j+1)%lon;f.extend([[0,2+j,2+q],[1,2+(lat-2)*lon+q,2+(lat-2)*lon+j]])
  for i in range(lat-2):
   for j in range(lon):q=(j+1)%lon;f.append([2+i*lon+j,2+(i+1)*lon+j,2+(i+1)*lon+q,2+i*lon+q])
 elif k=='prism':
  p=e['points'];origin=p[0];p=[vec(a,origin) for a in p];normal=unit(cross(vec(p[1],p[0]),vec(p[2],p[0])));n=len(p)
  v=p+[[a[i]-normal[i]*e['th'] for i in range(3)] for a in p]
  f=[list(range(n)),list(range(2*n-1,n-1,-1))]+[[(i+1)%n,i,i+n,(i+1)%n+n] for i in range(n)];tr=transform(origin)
 else:raise ValueError('Unsupported primitive '+k)
 if e.get('rotation'):raise ValueError('Unimplemented rotation '+str(e['id']))
 # Check every closed mesh before serializing it. C API subsequently welds edges.
 edges=Counter(tuple(sorted((a,face[(i+1)%len(face)]))) for face in f for i,a in enumerate(face))
 assert all(n==2 for n in edges.values()),('mesh not closed',e['id'])
 return v,f,tr

class API:
 def __init__(self,directory):
  self.handle=os.add_dll_directory(str(directory));self.dll=C.CDLL(str(directory/'SketchUpAPI.dll'))
  specs={
   'SUModelCreate':[PR],'SUModelRelease':[PR],'SUModelCreateFromFile':[PR,S],'SUModelSaveToFile':[R,S],
   'SUModelGetEntities':[R,PR],'SUModelSetName':[R,S],'SUModelAddComponentDefinitions':[R,N,PR],
   'SUComponentDefinitionCreate':[PR],'SUComponentDefinitionSetName':[R,S],'SUComponentDefinitionGetEntities':[R,PR],
   'SUComponentDefinitionCreateInstance':[R,PR],'SUComponentInstanceSetName':[R,S],
   'SUComponentInstanceSetTransform':[R,C.POINTER(Matrix)],'SUComponentInstanceGetTransform':[R,C.POINTER(Matrix)],
   'SUComponentInstanceGetDefinition':[R,PR],'SUEntitiesAddInstance':[R,R,PR],
   'SUGroupCreate':[PR],'SUGroupSetName':[R,S],'SUGroupGetName':[R,PR],'SUGroupGetEntities':[R,PR],
   'SUEntitiesAddGroup':[R,R],'SUEntitiesFill':[R,R,B],
   'SUGeometryInputCreate':[PR],'SUGeometryInputRelease':[PR],'SUGeometryInputSetVertices':[R,N,C.POINTER(Point)],
   'SULoopInputCreate':[PR],'SULoopInputAddVertexIndex':[R,N],'SUGeometryInputAddFace':[R,PR,PN],
   'SUGeometryInputFaceSetFrontMaterial':[R,N,C.POINTER(MatInput)],'SUGeometryInputFaceSetBackMaterial':[R,N,C.POINTER(MatInput)],
   'SUMaterialCreate':[PR],'SUMaterialSetName':[R,S],'SUMaterialSetColor':[R,C.POINTER(Color)],
   'SUMaterialSetOpacity':[R,D],'SUMaterialSetUseOpacity':[R,B],'SUMaterialSetTexture':[R,R],'SUModelAddMaterials':[R,N,PR],
   'SUTextureCreateFromFile':[PR,S,D,D],'SUTextureGetDimensions':[R,PN,PN,C.POINTER(D),C.POINTER(D)],
   'SUAttributeDictionaryCreate':[PR,S],'SUEntityAddAttributeDictionary':[R,R],
   'SUAttributeDictionarySetValue':[R,S,R],'SUAttributeDictionaryGetValue':[R,S,PR],
   'SUEntityGetAttributeDictionary':[R,S,PR],'SUModelGetAttributeDictionary':[R,S,PR],
   'SUTypedValueCreate':[PR],'SUTypedValueSetString':[R,S],'SUTypedValueRelease':[PR],'SUTypedValueGetString':[R,PR],
   'SUStringCreate':[PR],'SUStringRelease':[PR],'SUStringGetUTF8Length':[R,PN],'SUStringGetUTF8':[R,N,S,PN],
   'SUEntitiesGetNumGroups':[R,PN],'SUEntitiesGetGroups':[R,N,PR,PN],
   'SUEntitiesGetNumInstances':[R,PN],'SUEntitiesGetInstances':[R,N,PR,PN],
   'SUEntitiesGetNumEdges':[R,B,PN],'SUEntitiesGetEdges':[R,B,N,PR,PN],
   'SUEntitiesGetNumFaces':[R,PN],'SUEdgeGetNumFaces':[R,PN],
   'SUEdgeGetStartVertex':[R,PR],'SUEdgeGetEndVertex':[R,PR],'SUVertexGetPosition':[R,C.POINTER(Point)],
   'SUEntitiesGetBoundingBox':[R,C.POINTER(Bounds)],
   'SULayerCreate':[PR],'SULayerSetName':[R,S],'SUModelAddLayers':[R,N,PR],'SUDrawingElementSetLayer':[R,R],
   'SUSceneCreate':[PR],'SUSceneSetName':[R,S],'SUModelAddScenes':[R,N,PR],
   'SUSceneSetUseCamera':[R,B],'SUSceneSetCamera':[R,R],'SUModelGetNumScenes':[R,PN],
   'SUModelGetScenes':[R,N,PR,PN],'SUSceneGetCamera':[R,PR],'SUSceneGetName':[R,PR],
   'SUModelGetCamera':[R,PR],'SUCameraGetPerspectiveFrustumFOV':[R,C.POINTER(D)],
   'SUCameraGetOrientation':[R,C.POINTER(Point),C.POINTER(Point),C.POINTER(Point)],
   'SUCameraCreate':[PR],'SUCameraSetOrientation':[R,C.POINTER(Point),C.POINTER(Point),C.POINTER(Point)],
   'SUCameraSetPerspective':[R,B],'SUCameraSetPerspectiveFrustumFOV':[R,D],
   'SUModelSetCamera':[R,PR],'SUCameraRelease':[PR],
   'SUModelGetNumMaterials':[R,PN],'SUModelGetMaterials':[R,N,PR,PN],'SUMaterialGetTexture':[R,PR],'SUMaterialGetName':[R,PR],
   'SUModelGetOptionsManager':[R,PR],'SUOptionsManagerGetOptionsProviderByName':[R,S,PR],
   'SUOptionsProviderSetValue':[R,S,R],'SUTypedValueSetInt32':[R,C.c_int32],
   'SUModelGetRenderingOptions':[R,PR],'SURenderingOptionsSetValue':[R,S,R],'SUTypedValueSetBool':[R,B],
  }
  for name,args in specs.items():f=getattr(self.dll,name);f.argtypes=args;f.restype=C.c_int
  for name in ['SUComponentInstanceToEntity','SUGroupToEntity','SUGroupToDrawingElement','SUComponentInstanceToDrawingElement']:
   f=getattr(self.dll,name);f.argtypes=[R];f.restype=R
  self.dll.SUInitialize()
 def call(self,name,*args):
  result=getattr(self.dll,name)(*args)
  if result:raise RuntimeError(f'{name} failed: SUResult={result}')
 def create(self,name):r=R();self.call(name,C.byref(r));return r
 def get(self,name,obj):r=R();self.call(name,obj,C.byref(r));return r
 def string(self,r):
  n=N();self.call('SUStringGetUTF8Length',r,C.byref(n));b=C.create_string_buffer(n.value+1);out=N();self.call('SUStringGetUTF8',r,len(b),b,C.byref(out));return b.value.decode('utf-8')
 def attr(self,entity,data):
  dictionary=R();self.call('SUAttributeDictionaryCreate',C.byref(dictionary),b'DWG_TWIN');self.call('SUEntityAddAttributeDictionary',entity,dictionary)
  for key,v in data.items():
   value=self.create('SUTypedValueCreate');self.call('SUTypedValueSetString',value,enc(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False)));self.call('SUAttributeDictionarySetValue',dictionary,enc(key),value);self.call('SUTypedValueRelease',C.byref(value))
 def read_attr(self,entity,key):
  dictionary=self.get_attr_dictionary(entity);value=self.create('SUTypedValueCreate');self.call('SUAttributeDictionaryGetValue',dictionary,enc(key),C.byref(value));s=self.create('SUStringCreate');self.call('SUTypedValueGetString',value,C.byref(s));text=self.string(s);self.call('SUStringRelease',C.byref(s));self.call('SUTypedValueRelease',C.byref(value));return text
 def get_attr_dictionary(self,entity):
  r=R();self.call('SUEntityGetAttributeDictionary',entity,b'DWG_TWIN',C.byref(r));return r
 def count(self,name,obj,*args):n=N();self.call(name,obj,*args,C.byref(n));return n.value
 def array(self,countname,getname,obj,*args):
  n=self.count(countname,obj,*args);out=(R*n)();written=N();self.call(getname,obj,*args,n,out,C.byref(written));assert written.value==n;return out
 def close(self):self.dll.SUTerminate()

def build(api,root,scene,config,path):
 model=api.create('SUModelCreate');entities=api.get('SUModelGetEntities',model);api.call('SUModelSetName',model,enc(config.get('title',config.get('name','Jetis R02'))))
 manager=api.get('SUModelGetOptionsManager',model);provider=R();api.call('SUOptionsManagerGetOptionsProviderByName',manager,b'UnitsOptions',C.byref(provider))
 for key,val in [('LengthUnit',4),('LengthFormat',0),('LengthPrecision',3)]:
  typed=api.create('SUTypedValueCreate');api.call('SUTypedValueSetInt32',typed,val);api.call('SUOptionsProviderSetValue',provider,enc(key),typed);api.call('SUTypedValueRelease',C.byref(typed))
 render=api.get('SUModelGetRenderingOptions',model)
 for key,val in [('DisplayColorByLayer',False)]:
  typed=api.create('SUTypedValueCreate');api.call('SUTypedValueSetBool',typed,val);api.call('SURenderingOptionsSetValue',render,enc(key),typed);api.call('SUTypedValueRelease',C.byref(typed))
 for key,val in [('RenderMode',2),('EdgeDisplayMode',0)]:
  typed=api.create('SUTypedValueCreate');api.call('SUTypedValueSetInt32',typed,val);api.call('SURenderingOptionsSetValue',render,enc(key),typed);api.call('SUTypedValueRelease',C.byref(typed))
 dictionary=R();api.call('SUModelGetAttributeDictionary',model,b'DWG_TWIN',C.byref(dictionary))
 for key,val in [('source_filename',config.get('source_filename','')),('source_sha256',config.get('source_sha256','')),('scene_sha256',hashlib.sha256((root/'web/dist/assets/scene.json').read_bytes()).hexdigest()),('assumptions',scene.get('assumptions',[])),('native_method','Offline installed SketchUp 2023 C API; no MCP')]:
  typed=api.create('SUTypedValueCreate');api.call('SUTypedValueSetString',typed,enc(val if isinstance(val,str) else json.dumps(val,ensure_ascii=False)));api.call('SUAttributeDictionarySetValue',dictionary,enc(key),typed);api.call('SUTypedValueRelease',C.byref(typed))
 mats={};textures=[]
 for name,spec in scene['materials'].items():
  mat=api.create('SUMaterialCreate');api.call('SUMaterialSetName',mat,enc('DWG_TWIN '+name));color=spec['color'].lstrip('#');c=Color(*(int(color[i:i+2],16) for i in [0,2,4]),255);api.call('SUMaterialSetColor',mat,C.byref(c))
  api.call('SUMaterialSetOpacity',mat,spec.get('opacity',1));api.call('SUMaterialSetUseOpacity',mat,spec.get('opacity',1)<1)
  api.call('SUModelAddMaterials',model,1,(R*1)(mat.value))
  if spec.get('texture'):
   # Creation uses physical size; GetDimensions returns its reciprocal scale.
   # Verified against the R01 file made by SketchUp Ruby Texture#size.
   scale=spec.get('tile',2)*INCH
   tex=R();api.call('SUTextureCreateFromFile',C.byref(tex),enc(root/('web/dist/assets/textures/'+spec['texture']+'_Color.jpg')),scale,scale);api.call('SUMaterialSetTexture',mat,tex);textures.append(name)
  mats[name]=mat
 groups={}
 for name in dict.fromkeys(e['group'] for e in scene['elements']):
  g=api.create('SUGroupCreate');api.call('SUEntitiesAddGroup',entities,g);api.call('SUGroupSetName',g,enc(name));layer=api.create('SULayerCreate');api.call('SULayerSetName',layer,enc('DWG_TWIN | '+name));api.call('SUModelAddLayers',model,1,(R*1)(layer.value));api.call('SUDrawingElementSetLayer',api.dll.SUGroupToDrawingElement(g),layer);groups[name]=api.get('SUGroupGetEntities',g)
 cache={};bounds={}
 for index,e in enumerate(scene['elements']):
  v,faces,tr=mesh(e);key=json.dumps([v,faces,e['mat']],separators=(',',':'))
  if key not in cache:
   definition=api.create('SUComponentDefinitionCreate');api.call('SUModelAddComponentDefinitions',model,1,(R*1)(definition.value));api.call('SUComponentDefinitionSetName',definition,enc('DT_'+str(len(cache))))
   ents=api.get('SUComponentDefinitionGetEntities',definition);geometry=api.create('SUGeometryInputCreate');vertices=(Point*len(v))(*(Point(*(a*INCH for a in p)) for p in v));api.call('SUGeometryInputSetVertices',geometry,len(v),vertices)
   material=MatInput();material.material=mats[e['mat']]
   for face in faces:
    loop=api.create('SULoopInputCreate')
    for vertex in face:api.call('SULoopInputAddVertexIndex',loop,vertex)
    fi=N();api.call('SUGeometryInputAddFace',geometry,C.byref(loop),C.byref(fi));api.call('SUGeometryInputFaceSetFrontMaterial',geometry,fi.value,C.byref(material));api.call('SUGeometryInputFaceSetBackMaterial',geometry,fi.value,C.byref(material))
   api.call('SUEntitiesFill',ents,geometry,True);api.call('SUGeometryInputRelease',C.byref(geometry));cache[key]=definition
  inst=R();api.call('SUComponentDefinitionCreateInstance',cache[key],C.byref(inst));api.call('SUComponentInstanceSetTransform',inst,C.byref(tr));api.call('SUComponentInstanceSetName',inst,enc(e['name']));api.call('SUEntitiesAddInstance',groups[e['group']],inst,None)
  api.attr(api.dll.SUComponentInstanceToEntity(inst),{'id':e['id'],'kind':e['kind'],'source':{k:value for k,value in e.items() if 'source' in k},'motion':e.get('motion',''),'scene_element':e})
  pts=[world([p*INCH for p in a],tr) for a in v];bounds[e['id']]=[list(map(min,zip(*pts))),list(map(max,zip(*pts)))]
  if (index+1)%500==0:print('built',index+1,flush=True)
 for view_index,(name,view) in enumerate(config['views'].items()):
  camera=api.create('SUCameraCreate');eye=Point(*(x*INCH for x in view['eye']));target=Point(*(x*INCH for x in view['target']));up=Point(0,0,1)
  api.call('SUCameraSetOrientation',camera,C.byref(eye),C.byref(target),C.byref(up));api.call('SUCameraSetPerspective',camera,True);api.call('SUCameraSetPerspectiveFrustumFOV',camera,42)
  page=api.create('SUSceneCreate');api.call('SUSceneSetName',page,enc(view.get('title',name)));api.call('SUModelAddScenes',model,1,(R*1)(page.value));api.call('SUSceneSetUseCamera',page,True);api.call('SUSceneSetCamera',page,camera)
  # SUSceneSetCamera copies properties. SUModelSetCamera transfers ownership.
  if view_index==0:api.call('SUModelSetCamera',model,C.byref(camera))
  else:api.call('SUCameraRelease',C.byref(camera))
 path.parent.mkdir(exist_ok=True);api.call('SUModelSaveToFile',model,enc(path));api.call('SUModelRelease',C.byref(model))
 return {'method':'installed SketchUp 2023 C API offline','elements':len(scene['elements']),'definitions':len(cache),'groups':len(groups),'materials':len(mats),'texture_materials':textures,'path':str(path),'errors':[],'expected_bounds':bounds}

def audit(api,root,scene,path,expected):
 model=R();api.call('SUModelCreateFromFile',C.byref(model),enc(path));ents=api.get('SUModelGetEntities',model)
 objects={};defs={};bad=[];bboxerrors=[];source_elements={e['id']:e for e in scene['elements']}
 for group in api.array('SUEntitiesGetNumGroups','SUEntitiesGetGroups',ents):
  container=api.get('SUGroupGetEntities',group)
  for inst in api.array('SUEntitiesGetNumInstances','SUEntitiesGetInstances',container):
   eid=api.read_attr(api.dll.SUComponentInstanceToEntity(inst),'id');assert eid not in objects
   native_element=json.loads(api.read_attr(api.dll.SUComponentInstanceToEntity(inst),'scene_element'));assert native_element==source_elements[eid],('native properties differ',eid)
   definition=api.get('SUComponentInstanceGetDefinition',inst);tr=Matrix();api.call('SUComponentInstanceGetTransform',inst,C.byref(tr));de=api.get('SUComponentDefinitionGetEntities',definition)
   if definition.value not in defs:
    verts=[];nonmanifold=0;edges=api.array('SUEntitiesGetNumEdges','SUEntitiesGetEdges',de,False)
    for edge in edges:
     if api.count('SUEdgeGetNumFaces',edge)!=2:nonmanifold+=1
     for func in ['SUEdgeGetStartVertex','SUEdgeGetEndVertex']:
      vr=api.get(func,edge);pt=Point();api.call('SUVertexGetPosition',vr,C.byref(pt));verts.append([pt.x,pt.y,pt.z])
    defs[definition.value]=(verts,nonmanifold,api.count('SUEntitiesGetNumFaces',de))
   pts,nonmanifold,numfaces=defs[definition.value]
   assert pts and numfaces>0,(eid,'empty geometry')
   actual=[list(map(min,zip(*(world(p,tr) for p in pts)))),list(map(max,zip(*(world(p,tr) for p in pts))))]
   exp=expected[eid];err=max(abs(a-b) for aa,bb in zip(actual,exp) for a,b in zip(aa,bb))
   if err>1e-5:bboxerrors.append({'id':eid,'error_m':err})
   if nonmanifold:bad.append({'id':eid,'edges':nonmanifold})
   objects[eid]={'bounds_m':actual,'faces':numfaces,'kind':api.read_attr(api.dll.SUComponentInstanceToEntity(inst),'kind')}
 ids={e['id'] for e in scene['elements']};assert set(objects)==ids,('native IDs differ',len(objects),len(ids));assert not bad,('nonmanifold',bad[:10]);assert not bboxerrors,('bbox errors',bboxerrors[:10])
 materials=api.array('SUModelGetNumMaterials','SUModelGetMaterials',model);texture_count=0;texture_scales={}
 for mat in materials:
  texture=R();code=api.dll.SUMaterialGetTexture(mat,C.byref(texture))
  if code==0 and texture.value:
   w,h=N(),N();ss,tt=D(),D();api.call('SUTextureGetDimensions',texture,C.byref(w),C.byref(h),C.byref(ss),C.byref(tt));assert w.value>0 and h.value>0;texture_count+=1
   name=api.create('SUStringCreate');api.call('SUMaterialGetName',mat,C.byref(name));key=api.string(name).removeprefix('DWG_TWIN ');api.call('SUStringRelease',C.byref(name));tile=1/ss.value/INCH;assert abs(tile-scene['materials'][key].get('tile',2))<1e-8;texture_scales[key]=tile
 scene_count=api.count('SUModelGetNumScenes',model);camera_checks=[];views=json.loads((root/'web/dist/project.json').read_text())['views']
 for page,view in zip(api.array('SUModelGetNumScenes','SUModelGetScenes',model),views.values()):
  camera=api.get('SUSceneGetCamera',page);fov=D();api.call('SUCameraGetPerspectiveFrustumFOV',camera,C.byref(fov));assert abs(fov.value-42)<1e-8
  eye,target,up=Point(),Point(),Point();api.call('SUCameraGetOrientation',camera,C.byref(eye),C.byref(target),C.byref(up))
  for actual,wanted in [(eye,view['eye']),(target,view['target'])]:assert max(abs(getattr(actual,k)/INCH-v) for k,v in zip(['x','y','z'],wanted))<1e-8
  camera_checks.append({'title':view['title'],'fov_degrees':fov.value,'passed':True})
 assert scene_count==len(views)
 bb=Bounds();api.call('SUEntitiesGetBoundingBox',ents,C.byref(bb));bounds=[[getattr(p,k)/INCH for k in ('x','y','z')] for p in [bb.minimum,bb.maximum]]
 api.call('SUModelRelease',C.byref(model))
 return {'reloaded':True,'method':'native C API read-back; desktop UI not used','elements_expected':len(ids),'elements_actual':len(objects),'nonmanifold_solids':len(bad),'bbox_errors':bboxerrors,'scenes':scene_count,'camera_checks':camera_checks,'texture_materials':texture_count,'texture_tiles_m':texture_scales,'bounds_m':bounds,'objects':objects,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'passed':True}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--project',type=Path,required=True);parser.add_argument('--dll-dir',type=Path,default=Path(r'C:\Program Files\SketchUp\SketchUp 2023'));parser.add_argument('--output',type=Path);parser.add_argument('--audit-only',action='store_true');args=parser.parse_args()
 root=args.project;scene=json.loads((root/'web/dist/assets/scene.json').read_text());config=json.loads((root/'web/dist/project.json').read_text());output=args.output or root/'outputs/model.skp';proof=root/'verification';proof.mkdir(exist_ok=True)
 api=API(args.dll_dir)
 try:
  if args.audit_only:
   expected={}
   for e in scene['elements']:
    v,f,tr=mesh(e);pts=[world([p*INCH for p in a],tr) for a in v];expected[e['id']]=[list(map(min,zip(*pts))),list(map(max,zip(*pts)))]
  else:
   report=build(api,root,scene,config,output);expected=report.pop('expected_bounds');(proof/'native-sdk-build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
  result=audit(api,root,scene,output,expected);(proof/'native-sdk-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='objects'},ensure_ascii=False))
 finally:api.close()
if __name__=='__main__':main()
