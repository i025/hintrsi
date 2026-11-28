"""Anonymous RGB-only human forms with separate scene-level split exports."""
import html
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03b_teacher_alignment'
CATEGORIES = [
    ('object_identification_omission', '物体识别与遗漏'),
    ('relative_position_layout', '相对位置及布局'), ('orientation', '物体朝向'),
    ('relative_proportion', '相对比例'), ('geometry_parts_connections', '几何和部件连接'),
    ('material_texture', '材质与贴图'), ('camera_composition', '相机与构图'),
    ('lighting_shadow', '光照与阴影'), ('other', '其他'),
]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def field(identifier):
    options = '<option value="">请选择</option>' + ''.join('<option value="' + key + '">' + name + '</option>' for key, name in CATEGORIES)
    parts = ['<label>整体恢复度（0–100，粗粒度即可） <input name="' + identifier + ':score" type="number" min="0" max="100" step="5" placeholder="未评分"></label>']
    for priority in range(1, 4):
        name = identifier + ':defect' + str(priority)
        parts.append('<div class="defect"><b>重要缺陷 ' + str(priority) + '</b> <select name="' + name + ':category">' + options + '</select>' +
                     '<select name="' + name + ':severity"><option value="">严重度（可选）</option><option value="low">轻微</option><option value="medium">中等</option><option value="high">严重</option></select>' +
                     '<input name="' + name + ':description" placeholder="简单描述物体和可见问题（可选）"></div>')
    parts.append('<label>其他意见（可选）<textarea name="' + identifier + ':comment"></textarea></label>')
    return ''.join(parts)


def build(split):
    path = EXP / 'configs' / (split + '_cases.json')
    if not path.exists():
        return
    cases = json.loads(path.read_text())
    directory = EXP / 'human_review' / split
    directory.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for case in cases:
        grouped.setdefault(case['reference_group'], []).append(case)
    content, pair_records = [], []
    for group_index, records in enumerate(grouped.values(), 1):
        group = ('D' if split == 'development' else 'I') + 'Scene' + str(group_index)
        shutil.copyfile(Path(records[0]['seed']) / 'reference.png', directory / (group + '-reference.png'))
        content.append('<section><h2>参考场景 ' + str(group_index) + '</h2><img class="reference" src="' + group + '-reference.png" alt="参考图"><div class="grid">')
        for case in records:
            identifier = case['anonymous_id']
            shutil.copyfile(Path(case['seed']) / 'final.png', directory / (identifier + '.png'))
            content.append('<article><h3>' + identifier + '</h3><img src="' + identifier + '.png" alt="匿名重建">' + field(identifier) + '</article>')
        content.append('</div><h3>同一参考图下的相对偏好</h3><p>按恢复参考图的忠实程度比较，不以更漂亮为标准。未判断可留空。</p>')
        for i, first in enumerate(records):
            for second in records[i + 1:]:
                pair = first['anonymous_id'] + '_' + second['anonymous_id']
                pair_records.append({'id': pair, 'first': first['anonymous_id'], 'second': second['anonymous_id'], 'reference_group': group})
                content.append('<label class="pair">A=' + first['anonymous_id'] + '，B=' + second['anonymous_id'] + ' <select name="pair:' + pair + '"><option value="">未判断</option><option value="A">A 更好</option><option value="B">B 更好</option><option value="similar">相近</option><option value="uncertain">无法判断</option></select></label>')
        content.append('</section>')
    metadata = {'schema_version': 1, 'annotation_kind': 'human', 'split': split,
                'case_ids': [case['anonymous_id'] for case in cases], 'pairs': pair_records}
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>场景重建：匿名人工评价</title>
<style>body{font:16px system-ui;margin:24px auto;max-width:1500px;background:#f3f5f7;color:#17212b}h1,p{margin:16px}section{background:white;padding:20px;margin:20px 0;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}article{border:1px solid #ddd;padding:12px}img{width:100%;height:auto}.reference{max-width:960px;display:block;margin:auto}label{display:block;margin:12px 0}input,select,textarea,button{font:inherit;max-width:100%;padding:7px}textarea{width:96%;height:50px}.defect{padding:9px 0}.defect input{display:block;width:96%;margin-top:5px}.pair{display:inline-block;margin:8px 20px 8px 0}.toolbar{position:sticky;top:0;padding:12px;background:#e3edf7;z-index:2}button{cursor:pointer}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style>
<h1>场景重建：匿名人工评价</h1><p>比较真实参考图与匿名重建图，只判断能看到的恢复程度。无需阅读代码或提出技术方案。每例可填写评分、按重要性排列的最多3个缺陷及可选说明。没有确定判断时留空或选择无法判断。</p>
<p>SPLIT_DESCRIPTION</p><form id="review"><div class="toolbar"><label>评价者标识（可选） <input name="reviewer" placeholder="例如：自选昵称"></label><button type="button" id="export">导出本组人工评价 JSON</button><span id="saved"></span></div>
BODY
<p>参考图来源：<a href="https://huggingface.co/datasets/IDEAL-Benchmark/IDEAL-Scenes">IDEAL-Scenes</a>，CC BY 4.0。重建图为本实验真实输出。</p>
</form><script>
const metadata=METADATA;
const pageOpenedAt=new Date();
const form=document.querySelector('#review');
const storageKey='scene-rsi-03b-'+metadata.split;
const restored=JSON.parse(localStorage.getItem(storageKey)||'{}');
for(const element of form.elements){if(element.name && restored[element.name]!==undefined)element.value=restored[element.name];}
function values(){return Object.fromEntries(new FormData(form).entries());}
form.addEventListener('input',()=>{localStorage.setItem(storageKey,JSON.stringify(values()));document.querySelector('#saved').textContent=' 已保存在当前浏览器';});
document.querySelector('#export').onclick=()=>{
 const data=values(); const ratings=metadata.case_ids.map(id=>({anonymous_id:id,overall_fidelity:data[id+':score']===''?null:Number(data[id+':score']),defects:[1,2,3].map(priority=>({priority,category:data[id+':defect'+priority+':category'],severity:data[id+':defect'+priority+':severity']||null,description:data[id+':defect'+priority+':description']||''})).filter(item=>item.category),comment:data[id+':comment']||''}));
 const preferences=metadata.pairs.map(pair=>({...pair,preference:data['pair:'+pair.id]||null}));
 const result={schema_version:1,annotation_kind:'human',split:metadata.split,reviewer:data.reviewer||null,exported_at:new Date().toISOString(),page_opened_at:pageOpenedAt.toISOString(),seconds_since_page_open:(new Date()-pageOpenedAt)/1000,timing_scope:'Browser page-open interval, not verified active annotation time.',ratings,preferences};
 const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));link.download='experiment03b-'+metadata.split+'-human.json';link.click();URL.revokeObjectURL(link.href);
};</script></html>'''
    description = '开发材料：用于未来教师调整。' if split == 'development' else '独立评价材料：请单独导出；此组标注不得用于教师调整。'
    page = page.replace('SPLIT_DESCRIPTION', description).replace('BODY', ''.join(content)).replace('METADATA', json.dumps(metadata, ensure_ascii=False))
    (directory / 'index.html').write_text(page)
    write(EXP / 'human_review' / (split + '_blank_ratings.json'),
          {'annotation_kind': 'unannotated_template', 'split': split, 'ratings': [{'anonymous_id': case['anonymous_id'], 'overall_fidelity': None, 'defects': [], 'comment': None} for case in cases], 'preferences': [{'id': pair['id'], 'preference': None} for pair in pair_records]})
    print('Built anonymous form:', directory)


if __name__ == '__main__':
    build('development')
    build('independent')
