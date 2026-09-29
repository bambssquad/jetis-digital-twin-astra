require 'json'
require 'digest'
module DwgTwinAudit
 def self.run
  root=File.expand_path('..',__dir__)
  expected=JSON.parse(File.read(root+'/web/dist/assets/scene.json'))['elements'].map{|e|e['id']}.sort
  m=Sketchup.active_model
  raise 'Reopen the saved project SKP first' unless File.expand_path(m.path)==File.expand_path(root+'/outputs/model.skp')
  solids=m.entities.grep(Sketchup::Group).flat_map{|g|g.entities.select{|e|e.respond_to?(:get_attribute) && e.get_attribute('DWG_TWIN','id')}}
  ids=solids.map{|e|e.get_attribute('DWG_TWIN','id')}.sort
  bad=solids.select{|e|!e.manifold?}.map{|e|e.get_attribute('DWG_TWIN','id')}
  report={path:m.path,sha256:Digest::SHA256.file(m.path).hexdigest,expected:expected.length,actual:ids.length,ids_match:ids==expected,nonmanifold:bad,scenes:m.pages.length,texture_materials:m.materials.count{|m|m.texture},bounds_m:[m.bounds.width,m.bounds.height,m.bounds.depth].map{|v|v.to_m},passed:ids==expected && bad.empty?}
  File.write(root+'/verification/native-reopened.json',JSON.pretty_generate(report))
  report
 end
end
