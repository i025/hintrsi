import bpy, json, sys, os
from collections import Counter
s=bpy.context.scene
out={'scene':bpy.data.filepath,'camera':None,'lights':[],'objects':[],'materials':[],'images':[]}
if s.camera:
 c=s.camera; out['camera']={'name':c.name,'matrix':[list(r) for r in c.matrix_world],'lens':c.data.lens,'type':c.data.type,'sensor':c.data.sensor_width}
for o in s.objects:
 d={'name':o.name,'type':o.type,'parent':o.parent.name if o.parent else None,'location':list(o.location),'rotation':list(o.rotation_euler),'scale':list(o.scale),'dimensions':list(o.dimensions),'matrix':[list(r) for r in o.matrix_world]}
 if o.type=='MESH': d.update(materials=[m.name if m else None for m in o.data.materials],uv=[u.name for u in o.data.uv_layers],vertices=len(o.data.vertices))
 if o.type=='LIGHT': out['lights'].append({'name':o.name,'type':o.data.type,'energy':o.data.energy,'matrix':d['matrix']})
 out['objects'].append(d)
for m in bpy.data.materials:
 d={'name':m.name,'nodes':[],'links':[]}
 if m.use_nodes and m.node_tree:
  for n in m.node_tree.nodes:
   q={'name':n.name,'type':n.bl_idname,'label':n.label}
   if n.type=='TEX_IMAGE': q['image']=n.image.name if n.image else None
   if n.type=='GROUP' and n.node_tree: q['group']=n.node_tree.name; q['group_nodes']=[x.bl_idname for x in n.node_tree.nodes]
   if n.type=='TEX_COORD': q['object']=n.object.name if n.object else None
   d['nodes'].append(q)
  d['links']=[[l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name] for l in m.node_tree.links]
 out['materials'].append(d)
for i in bpy.data.images: out['images'].append({'name':i.name,'path':i.filepath,'packed':bool(i.packed_file),'source':i.source,'size':list(i.size)})
path='/app/inspection_'+os.path.basename(os.path.dirname(bpy.data.filepath))+'.json'
with open(path,'w') as f: json.dump(out,f,indent=2)
print('INSPECTION',path,'objects',len(out['objects']),'materials',len(out['materials']),'images',len(out['images']))
