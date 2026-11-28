import bpy,json,sys,os
from mathutils import Vector
s=bpy.context.scene
out={'camera':None,'lights':[],'objects':[],'materials':[],'images':[],'world':str(s.world.name if s.world else None),'render':{'engine':s.render.engine,'resolution':[s.render.resolution_x,s.render.resolution_y]}}
def vec(v): return [round(float(x),5) for x in v]
if s.camera: out['camera']={'name':s.camera.name,'matrix':[vec(r) for r in s.camera.matrix_world],'lens':s.camera.data.lens,'sensor':s.camera.data.sensor_width,'type':s.camera.data.type}
for o in s.objects:
 d={'name':o.name,'type':o.type,'parent':o.parent.name if o.parent else None,'matrix':[vec(r) for r in o.matrix_world],'dimensions':vec(o.dimensions)}
 if o.type=='MESH': d.update({'materials':[m.name if m else None for m in o.data.materials],'uvs':[u.name for u in o.data.uv_layers],'vertices':len(o.data.vertices)})
 if o.type=='LIGHT': d.update({'energy':o.data.energy,'light_type':o.data.type,'color':vec(o.data.color)}); out['lights'].append(d)
 out['objects'].append(d)
def tree(t,depth=0):
 if not t or depth>3:return None
 return {'nodes':[{'name':n.name,'type':n.bl_idname,'image':n.image.name if n.bl_idname=='ShaderNodeTexImage' and n.image else None,'uv_map':getattr(n,'uv_map',None),'inputs':{i.name:str(i.default_value) for i in n.inputs if not i.is_linked and hasattr(i,'default_value')},'group':tree(n.node_tree,depth+1) if n.bl_idname=='ShaderNodeGroup' else None} for n in t.nodes], 'links':[[l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name] for l in t.links]}
for m in bpy.data.materials: out['materials'].append({'name':m.name,'nodes':tree(m.node_tree) if m.use_nodes else None})
for i in bpy.data.images: out['images'].append({'name':i.name,'path':i.filepath,'packed':bool(i.packed_file),'source':i.source,'size':list(i.size)})
with open('/app/research/gt_'+sys.argv[-1]+'.json','w') as f: json.dump(out,f,indent=2)
print('INSPECTED',sys.argv[-1],len(out['objects']),len(out['materials']),len(out['images']))
