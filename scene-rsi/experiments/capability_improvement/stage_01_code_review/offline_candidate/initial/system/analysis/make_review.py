"""Create actual render comparisons and an unfilled, offline human review form."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/experiment_01_natural_trajectories'
OUTPUT = EXPERIMENT / 'analysis/human_review'


def main():
    assert (EXPERIMENT / 'batch_finished.json').exists()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scenes = json.loads((ROOT / 'configs/scenes.json').read_text())['scenes']
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
    rows = []
    comparison = Image.new('RGB', (2560, 3 * 400), 'white')
    draw = ImageDraw.Draw(comparison)
    for index, scene in enumerate(scenes):
        sid = scene['id']
        sources = [Path(scene['reference'])] + [EXPERIMENT / 'runs' / (sid + '-R' + str(rep)) / 'workspace/final.png' for rep in range(1, 4)]
        cells = []
        panels = []
        for column, path in enumerate(sources):
            label = sid + (' Reference' if column == 0 else ' Run ' + str(column))
            draw.text((column * 640 + 10, index * 400 + 8), label, fill='black', font=font)
            if path.exists():
                image = Image.open(path).convert('RGB').resize((640, 360), Image.Resampling.LANCZOS)
                comparison.paste(image, (column * 640, index * 400 + 40))
                image.save(OUTPUT / (sid + ('-reference' if column == 0 else '-R' + str(column)) + '.png'))
                panels.append(image)
                source = sid + ('-reference' if column == 0 else '-R' + str(column)) + '.png'
                visual = '<img src="' + source + '" alt="' + label + '">'
            else:
                panels.append(None)
                visual = '<p>没有最终渲染</p>'
            form = ''
            if column:
                run = sid + '-R' + str(column)
                form = ('<label>恢复度（1—5）<select name="' + run + ':score"><option value="">未评分</option>' +
                        ''.join('<option>' + str(score) + '</option>' for score in range(1, 6)) +
                        '</select></label><label>视觉缺陷<textarea name="' + run + ':defects"></textarea></label>' +
                        '<label>最应优先改进什么<textarea name="' + run + ':priority"></textarea></label>')
            cells.append('<article><h3>' + label + '</h3>' + visual + form + '</article>')
        rows.append('<section><h2>' + sid + '</h2><div class="grid">' + ''.join(cells) + '</div>' +
                    '<label>三次结果比较<textarea name="' + sid + ':comparison"></textarea></label></section>')
        # Fixed image regions aid inspection; they are not aligned object-error measurements.
        crops = {'S01': [(0, 90, 290, 285), (210, 170, 440, 360)],
                 'S02': [(45, 85, 300, 325), (280, 0, 475, 280)],
                 'S03': [(0, 70, 260, 330), (300, 95, 640, 360)]}[sid]
        for number, box in enumerate(crops, 1):
            strip = Image.new('RGB', (4 * 480, 310), 'white')
            for column, image in enumerate(panels):
                if image:
                    strip.paste(image.crop(box).resize((480, 280), Image.Resampling.LANCZOS), (column * 480, 30))
            ImageDraw.Draw(strip).text((8, 5), sid + ' fixed image-region crop ' + str(number) + ': reference | R1 | R2 | R3', fill='black', font=font)
            strip.save(OUTPUT / (sid + '-crop-' + str(number) + '.png'))
    comparison.save(OUTPUT / 'comparison.png')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>自然重建轨迹：人工评价</title>
<style>body{font:16px system-ui,sans-serif;background:#f3f5f7;margin:24px;color:#182330}main{max-width:1800px;margin:auto}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}article,section{background:white;border-radius:10px;padding:12px;margin-bottom:20px}img{width:100%;background:#ddd}h3{font-size:16px}label{display:block;margin:10px 0}textarea{width:96%;min-height:65px}button,select{padding:9px;font:inherit}button{cursor:pointer}@media(max-width:900px){.grid{grid-template-columns:1fr 1fr}}</style>
<main><h1>自然重建轨迹：人工评价</h1><p>比较参考图与三次独立重建。恢复度从 1（差异很大）到 5（非常接近）。请描述可见缺陷及改进优先级，无需阅读代码或提出 Blender 技术方案。</p><p>所有评分留空。本页面不会自动评价，也不会上传填写内容。完成后可下载本地评价文件。</p><form id="review">''' + ''.join(rows) + '''</form><button id="save">下载我的评价</button></main>
<script>document.querySelector('#save').onclick=()=>{const data={reviewer_type:'human',created_at:new Date().toISOString(),responses:Object.fromEntries(new FormData(document.querySelector('#review')))};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='human-review.json';a.click();URL.revokeObjectURL(a.href);};</script></html>'''
    (OUTPUT / 'index.html').write_text(page)
    (OUTPUT / 'README.txt').write_text('全部评分为空；未进行人工标注。comparison.png 为参考图 | R1 | R2 | R3。crop 文件是相同图像区域的裁剪，未作语义物体对齐，不能当成三维误差。')
    print(OUTPUT)


if __name__ == '__main__':
    main()
