"""Reuse the Experiment 01 offline form with anonymous before/after evidence."""
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'
OLD=ROOT/'experiments/experiment_01_natural_trajectories'
OUTPUT=EXP/'analysis/human_review'


def form(identifier):
    return ('<label>恢复度（1—5）<select name="'+identifier+':score"><option value="">未评分</option>'+
            ''.join('<option>'+str(i)+'</option>' for i in range(1,6))+'</select></label>'+
            '<label>可见缺陷<textarea name="'+identifier+':defects"></textarea></label>'+
            '<label>改进优先级<textarea name="'+identifier+':priority"></textarea></label>')


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    mapping=[r for r in json.loads((EXP/'configs/blind_order.json').read_text()) if (EXP/'runs'/r['run']).exists()]
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
    rows=[]
    crops={'S01':(120,130,510,360),'S02':(270,0,490,335),'S03':(320,120,640,360)}
    for scene in ('S01','S02','S03'):
        cards=[]
        for name,source,label in [('reference',EXP/'checkpoints'/scene/'reference.png','参考图'),
                                  ('initial',EXP/'checkpoints'/scene/'final.png','初始重建')]:
            image=Image.open(source).convert('RGB').resize((640,360),Image.Resampling.LANCZOS)
            image.save(OUTPUT/(scene+'-'+name+'.png'))
            image.crop(crops[scene]).resize((640,360)).save(OUTPUT/(scene+'-'+name+'-crop.png'))
            cards.append('<article><h3>'+label+'</h3><img src="'+scene+'-'+name+'.png">'+
                         (form(scene+'-initial') if name=='initial' else '')+'</article>')
        for record in mapping:
            if not record['run'].startswith(scene):continue
            ident=record['anonymous_id'];run=EXP/'runs'/record['run']
            image=Image.open(run/'workspace/final.png').convert('RGB').resize((640,360),Image.Resampling.LANCZOS)
            image.save(OUTPUT/(ident+'.png'));image.crop(crops[scene]).resize((640,360)).save(OUTPUT/(ident+'-crop.png'))
            links='<a href="'+ident+'-crop.png">固定图像区域局部</a>'
            for angle in (-15,15):
                source=run/'analysis/technical/capture'/('view_'+str(angle)+'.png')
                if source.exists():
                    Image.open(source).save(OUTPUT/(ident+'-view-'+str(angle)+'.png'))
                    links+=' · <a href="'+ident+'-view-'+str(angle)+'.png">补充视角 '+str(angle)+'°</a>'
            fixed=run/'analysis/technical/capture/target_geometry/fixed_camera_lighting.png'
            if fixed.exists():
                Image.open(fixed).save(OUTPUT/(ident+'-fixed.png'))
                links+=' · <a href="'+ident+'-fixed.png">初始相机与光照下的辅助图</a>'
            for chair in (1,2):
                support=run/'analysis/technical/capture/target_geometry'/('chair_'+str(chair)+'_support.png')
                if support.exists():
                    Image.open(support).save(OUTPUT/(ident+'-chair-'+str(chair)+'.png'))
                    links+=' · <a href="'+ident+'-chair-'+str(chair)+'.png">椅子 '+str(chair)+' 支撑诊断视角</a>'
            cards.append('<article><h3>'+ident+'</h3><img src="'+ident+'.png"><p>'+links+'</p>'+form(ident)+'</article>')
        rows.append('<section><h2>'+scene+'</h2><div class="grid">'+''.join(cards)+'</div>'+
                    '<label>哪些匿名结果更好，为什么？<textarea name="'+scene+':comparison"></textarea></label></section>')
    page=(OLD/'analysis/human_review/index.html').read_text()
    start=page.index('<form id="review">')+len('<form id="review">');end=page.index('</form>',start)
    page=page[:start]+''.join(rows)+page[end:]
    page=page.replace('自然重建轨迹：人工评价','场景改进：匿名人工评价')
    page=page.replace('比较参考图与三次独立重建。','比较参考图、初始重建与匿名改进结果。结果顺序已随机化，不显示实验组别。')
    page=page.replace('repeat(4,1fr)','repeat(3,1fr)').replace("a.download='human-review.json'","a.download='experiment02-human-review.json'")
    (OUTPUT/'index.html').write_text(page)
    (OUTPUT/'README.txt').write_text('复用 Experiment 01 评价表及本地导出逻辑。全部人工评分为空，不包含实验组名称或教师 Hint。局部图使用固定图像区域，未作语义或三维对齐。补充视角和固定相机光照图仅供辅助检查。')
    (EXP/'analysis/human_ratings.json').write_text(json.dumps([{'anonymous_id':r['anonymous_id'],'human_rating':None,'human_feedback':None} for r in mapping],indent=2))
    for repetition in (1,2):
        if not (EXP/'runs'/('S01-E0-R'+str(repetition))).exists():continue
        montage=Image.new('RGB',(7*480,3*300),'white');draw=ImageDraw.Draw(montage)
        for row,scene in enumerate(('S01','S02','S03')):
            sources=[('Reference',EXP/'checkpoints'/scene/'reference.png'),('Initial',EXP/'checkpoints'/scene/'final.png')]
            sources += [('E'+str(group),EXP/'runs'/(scene+'-E'+str(group)+'-R'+str(repetition))/'workspace/final.png') for group in range(5)]
            for col,(label,path) in enumerate(sources):
                draw.text((col*480+8,row*300+5),scene+' '+label,fill='black',font=font)
                if path.exists():montage.paste(Image.open(path).convert('RGB').resize((480,270),Image.Resampling.LANCZOS),(col*480,row*300+30))
        montage.save(EXP/'analysis'/('comparison_'+('core' if repetition==1 else 'repeat')+'.png'))
    print('Anonymous offline form and actual result montages:',OUTPUT)


if __name__=='__main__':main()
