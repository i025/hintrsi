"""Explicit posthoc annotations grounded in delivered code, states, and SDK events."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_01_natural_trajectories'
COMMON = ['parameterized_helpers', 'primitive_mesh_assembly', 'bevel_edges', 'weighted_normals',
          'constant_principled_materials', 'explicit_world_coordinates', 'relative_part_coordinates',
          'loop_repetition', 'perspective_look_at_camera', 'area_lighting', 'cycles_denoising',
          'geometry_surface_patterns']
OFFICE = ['custom_mesh_surfaces', 'subdivision_shells', 'solidify_shells', 'smooth_shading',
          'seeded_procedural_geometry', 'local_rotation_transforms', 'individual_floorboards']
EXTRA = {
'S01-R1': ['render_inspection', 'camera_revision'],
'S01-R2': [],
'S01-R3': ['render_inspection', 'camera_revision'],
'S02-R1': ['warm_point_lights', 'explicit_hinge_frame_transform'],
'S02-R2': ['warm_point_lights', 'parented_hinge_assembly'],
'S02-R3': ['warm_point_lights', 'parented_hinge_assembly', 'hollow_cabinet_panels', 'render_inspection', 'camera_revision'],
'S03-R1': ['custom_mesh_surfaces', 'procedural_noise_shader', 'anisotropic_texture_mapping', 'font_geometry', 'render_inspection', 'camera_revision'],
'S03-R2': ['custom_mesh_surfaces', 'geometry_marble_veins', 'seeded_procedural_geometry', 'solidify_leaves', 'individual_floorboards', 'render_inspection', 'camera_revision', 'lighting_revision'],
'S03-R3': ['custom_mesh_surfaces', 'geometry_marble_veins', 'seeded_procedural_geometry', 'ellipsoid_organic_detail', 'render_inspection', 'camera_revision'],
}
SEQUENCES = {
'S01-R1': ['materials','room','window','door','shelf','cabinet','lamp','desk','chairs','planter','lighting','camera'],
'S01-R2': ['materials','room','window','shelf','cabinet','door','desk','additional_table','chairs','lamp','planter','lighting','camera'],
'S01-R3': ['materials','room','window','shelf','cabinet','door','lamp','desk','chairs','planter','lighting','camera'],
'S02-R1': ['materials','room','shelf','cabinet','door','lamps','rug','bed','right_foreground_structure','left_wall','lighting','camera'],
'S02-R2': ['materials','room','shelf','cabinet','lamps','door','rug','bed','right_foreground_structure','left_wall','lighting','camera'],
'S02-R3': ['materials','room','shelf','cabinet','lamps','rug','bed','right_foreground_structure','door','lighting','camera'],
'S03-R1': ['materials','room','door','stove','rear_counter','right_cabinets','upper_cabinets','plant','lighting','camera'],
'S03-R2': ['materials','room','door','right_cabinets','upper_cabinets','stove','rear_counter','plant','lighting','camera'],
'S03-R3': ['materials','room','door','right_cabinets','upper_cabinets','rear_counter','stove','plant','lighting','camera'],
}
# Source-line evidence refers to executed final programs. Geometry was unchanged by revisions.
RANGES = {
'S01-R1': [1,88], 'S01-R2':[1,99], 'S01-R3':[1,88],
'S02-R1':[1,77], 'S02-R2':[1,78], 'S02-R3':[1,77],
'S03-R1':[1,66], 'S03-R2':[1,87], 'S03-R3':[1,77]}
UNIQUE_LINES = {
'S01-R1': {'custom_mesh_surfaces':[55,81], 'subdivision_shells':[71,71], 'solidify_shells':[71,71], 'seeded_procedural_geometry':[79,81], 'individual_floorboards':[20,26]},
'S01-R2': {'custom_mesh_surfaces':[64,91], 'subdivision_shells':[76,76], 'solidify_shells':[77,77], 'seeded_procedural_geometry':[89,91], 'individual_floorboards':[23,29]},
'S01-R3': {'custom_mesh_surfaces':[56,82], 'subdivision_shells':[69,69], 'solidify_shells':[70,70], 'seeded_procedural_geometry':[79,82], 'individual_floorboards':[20,27]},
'S02-R1': {'explicit_hinge_frame_transform':[44,52], 'warm_point_lights':[54,58]},
'S02-R2': {'parented_hinge_assembly':[54,62], 'warm_point_lights':[47,50]},
'S02-R3': {'parented_hinge_assembly':[64,71], 'hollow_cabinet_panels':[39,47], 'warm_point_lights':[49,51]},
'S03-R1': {'procedural_noise_shader':[9,10], 'anisotropic_texture_mapping':[9,10], 'font_geometry':[35,36], 'custom_mesh_surfaces':[54,57]},
'S03-R2': {'geometry_marble_veins':[37,40], 'seeded_procedural_geometry':[3,40], 'solidify_leaves':[73,76], 'individual_floorboards':[20,27], 'custom_mesh_surfaces':[73,76], 'lighting_revision':[80,80]},
'S03-R3': {'geometry_marble_veins':[31,33], 'seeded_procedural_geometry':[3,33], 'ellipsoid_organic_detail':[67,67], 'custom_mesh_surfaces':[63,66]}}

OFFICE_PARTS = {
'room:floor':['floor slab','floor substrate','floor base'], 'room:boards':['floor plank','timber floor plank','oak plank'],
'room:walls':['back wall','left wall','right wall'], 'room:baseboards':['baseboard','skirting'],
'window:frame':['window vertical','window horizontal','window side'], 'window:slats':['slat'],
'door:leaf':['dark door leaf','door dark slab','dark door'], 'door:panel_details':['raised door panel','recessed door panel','panel inset'],
'shelf:horizontal':['bookcase top','bookcase bottom','middle shelf','shelf top','shelf base','shelf horizontal'],
'shelf:dividers':['bookcase upright','shelf vertical divider','shelf divider'],
'cabinet:body':['white cabinet','white narrow cabinet','tall white cabinet'],
'cabinet:separate_front_panel':['cabinet front panel','cabinet front inset'],
'desk:top':['desk top'], 'desk:legs':['desk leg'], 'desk:additional_top':['second foreground tabletop'],
'chair:shell':['chair shell','molded shell'], 'chair:post':['chair central post','chair center column','central post'],
'chair:spokes':['five star chair base','chair five star spoke','caster arm'], 'chair:casters':['caster wheel',' wheel'],
'chair:separate_hub':['chair hub'], 'planter:pot':['teal round planter','large teal plant pot','teal planter'],
'planter:soil':['soil'], 'planter:leaves':['grass blade'],
'lamp:base':['lamp foot'],'lamp:stem':['lamp stem'],'lamp:shade':['lampshade']}
BEDROOM_PARTS = {
'room:floor':['floor'], 'room:walls':['wall'], 'room:baseboards':['skirting','baseboard'], 'room:tile_joints':['joint','grout'],
'bookcase:back':['shelf back','raised shelf back','bookshelf back','bookcase back','bookcase upper back'],
'bookcase:sides':['shelf left upright','shelf right upright','bookshelf side','bookcase side'],
'bookcase:shelves':['open shelf','bookshelf shelf','open bookshelf shelf'],
'cabinet:solid_carcass':['cabinet body'], 'cabinet:separate_sides':['cabinet side'],
'cabinet:separate_back':['cabinet back'], 'cabinet:internal_shelves':['cabinet shelf'],
'cabinet:opaque_glass_named_panes':['glass inset','cabinet glass pane','glass cabinet pane'],
'cabinet:lower_doors':['cabinet lower door','cabinet door bottom panel','lower cabinet door'],
'cabinet:frame':['cabinet front vertical frame','cabinet front horizontal frame','glass frame','glass door'],
'door:leaf':['open wooden door','natural oak door slab','wood door leaf'],
'door:panel_details':['recessed panel','door panel','recessed door panel'],
'door:hinge_empty':['open door hinge'], 'lamp:base':['lamp weighted base','lamp round base','floor lamp round base'],
'lamp:stem':['lamp slim stem','lamp slender stem','floor lamp slender stem'], 'lamp:shade':['lamp shade','lampshade'],
'bed:base':['wood bed base','bed timber base','bed wooden base'], 'bed:mattress':['mattress'],
'rug:slab':['rug'], 'right_foreground:panel':['right foreground white side panel','white bed end panel','right white bed end panel'],
'right_foreground:top':['right furniture top','right white furniture top'],
'right_foreground:additional_body':['white bed along right wall']}
KITCHEN_PARTS = {
'room:floor':['floor'], 'room:walls':['wall'], 'room:seam_geometry':['floor plank joint','staggered joint','plank joint','floor board seam','staggered end joint'],
'door:leaf':['open door','open white door'], 'door:opening':['door opening','doorway'],
'right_cabinets:carcass':['right cabinet carcass','right base cabinet','right cabinet body'],
'right_cabinets:countertop':['marble countertop','right marble counter','marble counter'],
'right_cabinets:fronts':['drawer front','lower cabinet door'], 'right_cabinets:pulls':['drawer pull','drawer knob','cabinet knob'],
'upper_cabinets:carcass':['upper cabinet boxes','upper cabinet','upper cabinets'],
'upper_cabinets:insets':['upper green inset','green inset'], 'upper_cabinets:pulls':['upper knob','upper cabinet pull'],
'stove:body':['range body','stove body'], 'stove:top':['range cooktop','range top rim','stovetop'],
'stove:burners':['hotplate','electric burner'], 'stove:console':['control backsplash','raised range control panel','raised control panel'],
'stove:dials':['stove dial','purple control dial','control dial'], 'stove:clock_text':['digital clock'],
'stove:oven_face':['oven door'], 'stove:handle':['oven handle'],
'rear_cabinet:body':['left cabinet','rear island cabinet'], 'rear_cabinet:aqua_top':['aqua countertop','aqua worktop'],
'plant:pot':['plant pot','flower pot'], 'plant:soil':['potting soil','pot soil','soil'],
'plant:stem':['plant stem','plant main stem'], 'plant:leaves':['plant leaf','pointed leaf'],
'plant:bud':['plant bud','tall bud','sphere'], 'countertop:geometric_veins':['marble vein']}

DEFECTS = {
'S01': [('composition_mismatch','scene','Foreground occupancy, viewpoint and relative object scale differ visibly from the reference.'),
        ('desk_surface_appearance','desk','Desk surface is much lighter and lacks the visible dark wood grain in the reference.')],
'S02': [('composition_mismatch','scene','Camera distance and bed/door coverage differ from the close reference view.'),
        ('door_occlusion_mismatch','door','Open door leaf does not occupy/occlude the central foreground region as in the reference.'),
        ('rug_texture_missing','rug','Named rug material is constant color; reference shows mottled surface variation.')],
'S03': [('composition_mismatch','scene','Corridor viewpoint and stove/counter framing differ from the reference.'),
        ('countertop_texture_mismatch','countertop','Countertop surface variation differs from the reference; methods differ across runs.'),
        ('directional_daylight_missing','lighting','Strong localized floor illumination/shadow in the reference is not recovered by the broad area-light setups.')]
}


def main():
    assert (EXP/'batch_finished.json').exists()
    runs={}
    for directory in sorted((EXP/'runs').iterdir()):
        name=directory.name; scene=name[:3]; state_path=directory/'analysis/technical/capture/final_state.json'
        state=json.loads(state_path.read_text()); event_path=directory/'analysis/sdk_events.json'; events=json.loads(event_path.read_text())
        source='runs/'+name+'/workspace/build.py'; state_ref='runs/'+name+'/analysis/technical/capture/final_state.json'
        labels=COMMON+(OFFICE if scene=='S01' else [])+EXTRA[name]
        strategies={label:{'status':'retained' if label not in ['render_inspection','camera_revision','lighting_revision'] else 'executed',
                           'source':source, 'source_lines':UNIQUE_LINES.get(name,{}).get(label,RANGES[name]),
                           'state_evidence':state_ref} for label in labels}
        tools=[]; tool_evidence=[]
        for ev in events:
            for block in ev['message'].get('content',[]):
                if 'name' not in block:continue
                tool=block['name']; inp=block['input']; label=None
                if tool=='Write':label='write_source'
                elif tool=='Read' and inp.get('file_path')=='/app/final.png':label='inspect_render'
                elif tool=='Edit':label='revise_camera'
                elif tool=='Bash':
                    command=inp['command']
                    if '--python /app/build.py' in command:
                        if 'Adjust camera' in inp.get('description',''):
                            tools.append('revise_camera')
                            if name=='S03-R2':tools.append('revise_lighting')
                        label='execute_scene'
                if label:
                    tools.append(label);tool_evidence.append({'operation':label,'event_index':ev['event_index'],'tool_call_id':block['id']})
        mappings={'S01':OFFICE_PARTS,'S02':BEDROOM_PARTS,'S03':KITCHEN_PARTS}[scene]
        parts={label:[obj['name'] for obj in state['objects'] if any(needle in obj['name'].lower() for needle in needles)]
               for label,needles in mappings.items()}
        if scene in ('S02','S03'):
            parts['room:floor']=[obj['name'] for obj in state['objects'] if obj['name'].lower()=='floor']
        parts={key:value for key,value in parts.items() if value}
        defects=[{'id':key,'object':obj,'observation':observation,'evidence':['analysis/human_review/comparison.png',source,state_ref],
                  'kind':'automated_visual_and_scene_observation'} for key,obj,observation in DEFECTS[scene]]
        if name=='S01-R2':defects.append({'id':'additional_visible_table','object':'desk','observation':'Additional foreground tabletop is visible where the reference shows the chair/floor region.','evidence':[source+':62','analysis/human_review/S01-R2.png'],'kind':'automated_observation'})
        runs[name]={'strategies':strategies,'construction_sequence':SEQUENCES[name],
                    'construction_sequence_evidence':{'source':source,'source_lines':RANGES[name],
                      'execution':'analysis/evidence_index.json:successful Blender captures; revisions changed camera parameters, plus S03-R2 light energies, without changing the construction order'},
                    'tool_sequence':tools,'tool_sequence_evidence':tool_evidence,
                    'state_components':list(parts),'state_component_evidence':parts,'state_file':state_ref,
                    'defects':defects,'unknown':['Hidden reasoning/planning','Unsaved intermediate geometric states','Exact mesh contact/penetration without a mesh-level test'],
                    'notes':['Parts are semantic geometry inventories, not GT name/mesh-count targets.',
                             'Bedroom right foreground object is a cropped bookcase in GT but visually ambiguous; alternative semantic interpretation is not scored as a confirmed defect.']}
    output={'annotation_kind':'Automated experiment-assistant review, not human annotation',
            'method':'Evidence-based exploratory ontology; one annotator, no inter-rater validation. Coarse labels can conceal important quantitative differences.',
            'absent_in_observed_code_and_final_states':['curve_or_NURBS_modeling','image_mapped_reference_plane','explicit_optimization_solver'],
            'sequences_scope':'Construction order in successful code; repeated full rebuilds represented separately by SDK tool cycles, not hidden reasoning.',
            'runs':runs}
    (EXP/'analysis/annotations.json').write_text(json.dumps(output,indent=2))
    print('Grounded annotations saved for',len(runs),'runs')

if __name__=='__main__':main()
