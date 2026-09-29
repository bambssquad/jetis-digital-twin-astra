require 'json'
module DwgTwinBuild
 ROOT=File.expand_path('..',__dir__)
 def self.p(v); Geom::Point3d.new(v.map{|x| x.to_f.m}); end
 def self.run
  @m=Sketchup.active_model
  raise 'Unexpected user model; build stopped' unless @m.path.empty? && @m.entities.length==0
  @scene=JSON.parse(File.read(ROOT+'/web/dist/assets/scene.json'))
  raise 'Scene is empty' if @scene['elements'].empty?
  @config=JSON.parse(File.read(ROOT+'/web/dist/project.json'))
  @m.start_operation('DWG_TWIN detailed source model',true)
  @m.options['UnitsOptions']['LengthUnit']=4
  @m.options['UnitsOptions']['LengthFormat']=0
  @m.options['UnitsOptions']['LengthPrecision']=3
  @m.set_attribute('DWG_TWIN','source',@config['source_filename'])
  @m.set_attribute('DWG_TWIN','assumptions',@scene['assumptions'].join("\n"))
  @m.set_attribute('DWG_TWIN','source_units',@config['unit_evidence'].join('; '))
  @materials={};@groups={};@defs={};@errors=[];@count=0
  @scene['materials'].each do |name,s|
   mat=@m.materials.add('DWG_TWIN '+name);mat.color=s['color'];mat.alpha=s.fetch('opacity',1)
   if s['texture']
    file=ROOT+'/web/dist/assets/textures/'+s['texture']+'_Color.jpg'
    mat.texture=file;mat.texture.size=[s.fetch('tile',2).m,s.fetch('tile',2).m]
   end
   @materials[name]=mat
  end
  @scene['elements'].map{|e|e['group']}.uniq.each do |name|
   g=@m.entities.add_group;g.name=name;g.layer=@m.layers.add('DWG_TWIN | '+name);@groups[name]=g
  end
  @index=0
  UI.start_timer(0.05,false){batch}
 end
 def self.face(ents,points,mat)
  f=ents.add_face(points.map{|a|p(a)});raise 'Degenerate face' unless f
  f.material=mat;f.back_material=mat;f
 end
 def self.boxdef(w,d,h,mat,key)
  return @defs[key] if @defs[key]
  definition=@m.definitions.add('DT '+key)
  v=[[0,0,0],[w,0,0],[w,d,0],[0,d,0],[0,0,h],[w,0,h],[w,d,h],[0,d,h]]
  [[3,2,1,0],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]].each{|ids|face(definition.entities,ids.map{|i|v[i]},mat)}
  @defs[key]=definition
 end
 def self.profiledef(e,mat,key)
  return @defs[key] if @defs[key]
  definition=@m.definitions.add('DT '+key);w=e['w'].to_f;h=e['h'].to_f;a=Geom::Point3d.new(e['a']);b=Geom::Point3d.new(e['b']);len=a.distance(b)
  if e['kind']=='beam'
   pts=[[-w/2,-h/2],[w/2,-h/2],[w/2,h/2],[-w/2,h/2]]
  elsif e['kind']=='wf'
   tw=e['tw'].to_f;tf=e['tf'].to_f;pts=[[-w/2,-h/2],[w/2,-h/2],[w/2,-h/2+tf],[tw/2,-h/2+tf],[tw/2,h/2-tf],[w/2,h/2-tf],[w/2,h/2],[-w/2,h/2],[-w/2,h/2-tf],[-tw/2,h/2-tf],[-tw/2,-h/2+tf],[-w/2,-h/2+tf]]
  else
   t=e['tw'].to_f;tf=e['tf'].to_f;pts=[[-w/2,-h/2],[w/2,-h/2],[w/2,-h/2+tf],[-w/2+t,-h/2+tf],[-w/2+t,h/2-tf],[w/2,h/2-tf],[w/2,h/2],[-w/2,h/2]]
  end
  lower=pts.map{|x,y|[x,y,0]};upper=pts.map{|x,y|[x,y,len]}
  face(definition.entities,lower.reverse,mat);face(definition.entities,upper,mat)
  pts.length.times{|i|j=(i+1)%pts.length;face(definition.entities,[lower[i],lower[j],upper[j],upper[i]],mat)}
  @defs[key]=definition
 end
 def self.build(e)
  mat=@materials[e['mat']];entities=@groups[e['group']].entities;kind=e['kind'];inst=nil
  case kind
  when 'box'
   key=[kind,e['s'],e['mat']].to_json;d=boxdef(*e['s'],mat,key);inst=entities.add_instance(d,Geom::Transformation.translation(p(e['p'])))
  when 'beam','wf','cnp'
   len=Geom::Point3d.new(e['a']).distance(Geom::Point3d.new(e['b']));key=[kind,e['w'],e['h'],e['tw'],e['tf'],len.round(6),e['mat']].to_json
   d=profiledef(e,mat,key);z=p(e['b'])-p(e['a']);z.normalize!
   ref=z.z.abs>0.99 ? Geom::Vector3d.new(0,1,0) : Geom::Vector3d.new(0,0,1)
   x=ref.cross(z);x.normalize!;y=z.cross(x);y.normalize!
   inst=entities.add_instance(d,Geom::Transformation.axes(p(e['a']),x,y,z))
  when 'cylinder','wheel'
   height=kind=='wheel' ? e['d'] : e['h']
   key=[kind,e['r'],height,e['mat']].to_json
   unless @defs[key]
    d=@m.definitions.add('DT '+key);edges=d.entities.add_circle(ORIGIN,Z_AXIS,e['r'].m,16);f=d.entities.add_face(edges);f.reverse! if f.normal.z<0;f.pushpull(height.m)
    d.entities.grep(Sketchup::Face).each{|ff|ff.material=mat;ff.back_material=mat};@defs[key]=d
   end
   tr=Geom::Transformation.translation(p(e['p']))
   if kind=='wheel'
    tr=Geom::Transformation.translation(p([e['p'][0],e['p'][1]+height/2,e['p'][2]]))*Geom::Transformation.rotation(ORIGIN,X_AXIS,Math::PI/2)
   end
   inst=entities.add_instance(@defs[key],tr)
  when 'sphere'
   key=[kind,e['s'],e['mat']].to_json
   unless @defs[key]
    d=@m.definitions.add('DT '+key);lat=6;lon=10;rings=[]
    (1...lat).each do |i|
     a=Math::PI*i/lat
     rings<<Array.new(lon){|j|b=2*Math::PI*j/lon;[e['s'][0]*Math.sin(a)*Math.cos(b),e['s'][1]*Math.sin(a)*Math.sin(b),e['s'][2]*Math.cos(a)]}
    end
    top=[0.0,0.0,e['s'][2]];bottom=[0.0,0.0,-e['s'][2]]
    lon.times do |j|
     k=(j+1)%lon
     face(d.entities,[top,rings[0][j],rings[0][k]],mat)
     face(d.entities,[bottom,rings[-1][k],rings[-1][j]],mat)
    end
    (0...rings.length-1).each do |i|
     lon.times do |j|
      k=(j+1)%lon
      face(d.entities,[rings[i][j],rings[i+1][j],rings[i+1][k],rings[i][k]],mat)
     end
    end
    @defs[key]=d
   end
   inst=entities.add_instance(@defs[key],Geom::Transformation.translation(p(e['p'])))
  when 'prism'
   inst=entities.add_group;pts=e['points'];normal=(p(pts[1])-p(pts[0])).cross(p(pts[2])-p(pts[0]));normal.normalize!;off=normal.to_a.map{|n|-n*e['th']}
   bottom=pts.map{|v|v.zip(off).map{|a,b|a+b}}
   face(inst.entities,pts,mat);face(inst.entities,bottom.reverse,mat)
   pts.length.times{|i|j=(i+1)%pts.length;face(inst.entities,[pts[j],pts[i],bottom[i],bottom[j]],mat)}
  end
  raise 'Unknown primitive' unless inst
  inst.name=e['name'];inst.set_attribute('DWG_TWIN','id',e['id']);inst.set_attribute('DWG_TWIN','kind',kind)
  inst.set_attribute('DWG_TWIN','motion',e['motion']) if e['motion']
  @count+=1
 end
 def self.batch
  last=[@index+200,@scene['elements'].length].min
  while @index<last
   e=@scene['elements'][@index]
   begin;build(e);rescue=>ex;@errors<<{id:e['id'],error:ex.message};end
   @index+=1
  end
  File.write(ROOT+'/verification/native-progress.json',JSON.generate({done:@index,total:@scene['elements'].length,errors:@errors.length}))
  if @index<@scene['elements'].length;UI.start_timer(0.01,false){batch};else;finish;end
 rescue=>ex
  File.write(ROOT+'/verification/native-fatal.txt',ex.full_message);@m.abort_operation
 end
 def self.finish
  @m.rendering_options['DisplayColorByLayer']=false
  @m.rendering_options['DrawEdges']=false
  @m.rendering_options['DrawProfiles']=false
  @m.rendering_options['FaceFrontColor']=Sketchup::Color.new(220,220,220)
  @m.rendering_options['RenderMode']=2
  @m.rendering_options['DisplaySky']=true
  @m.rendering_options['DisplayGround']=false
  @m.shadow_info['DisplayShadows']=true
  @m.shadow_info['Light']=75;@m.shadow_info['Dark']=35
  raise 'Geometry errors: '+@errors.to_json unless @errors.empty?
  @config['views'].each do |name,v|
   @m.active_view.camera=Sketchup::Camera.new(p(v['eye']),p(v['target']),[0,0,1])
   @m.active_view.camera.fov=42
   @m.pages.add(v['title'] || name)
  end
  @m.pages.selected_page=@m.pages[0]
  @m.commit_operation
  path=ROOT+'/outputs/model.skp';ok=@m.save(path)
  @m.active_view.write_image(filename:ROOT+'/outputs/model-native.png',width:2000,height:1400,antialias:true)
  report={saved:ok,path:path,version:Sketchup.version,pid:Process.pid,elements:@count,definitions:@defs.length,materials:@materials.length,groups:@groups.keys,scenes:@m.pages.length,errors:@errors,texture_materials:@materials.select{|k,v|v.texture}.keys}
  File.write(ROOT+'/verification/native-build.json',JSON.pretty_generate(report))
 end
end

