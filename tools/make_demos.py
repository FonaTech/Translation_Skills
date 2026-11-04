#!/usr/bin/env python3
"""Author-owned fixtures. No actual private source documents enter this repository."""
from pathlib import Path
import sys,json,subprocess
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'skills/document-translation/scripts'))
import translate as t
BASE=None
DATA=[
('research','Research note','The trial included 24 participants. The estimated difference was 2.4 points (95% CI, 0.3–4.5); the association does not establish causation.',
 {'zh-Hans':('试验纳入 24 名参与者。估计差异为 2.4 分（95% CI，0.3–4.5）；这一关联不能确立因果关系。','共有 24 人参加试验。估计差异是 2.4 分，95% CI 为 0.3–4.5。结果显示的是关联，不能据此认定存在因果关系。'),
 'ja':('試験には 24 人が参加した。推定差は 2.4 点（95% CI、0.3–4.5）であり、この関連は因果関係を立証しない。','参加者は 24 人だった。推定された差は 2.4 点で、95% CI は 0.3–4.5 だった。ただし、関連が見られても因果関係が示されたことにはならない。')}),
('manual','Equipment instruction','Disconnect the power before cleaning. Do not immerse the unit. Wait at least 30 seconds before reconnecting it.',
 {'zh-Hans':('清洁前断开电源。切勿将本机浸入液体。重新接通电源前，至少等待 30 秒。','先断开电源，再清洁设备；清洁时不得把整机浸入液体。完成后，至少等 30 秒再接通电源。'),
 'ar':('افصل الطاقة قبل التنظيف. لا تغمر الوحدة في سائل. انتظر 30 ثانية على الأقل قبل إعادة توصيلها.','قبل بدء التنظيف، افصل الطاقة. يجب ألا تُغمر الوحدة في سائل، وعليك الانتظار 30 ثانية على الأقل قبل توصيل الطاقة مرة أخرى.')}),
('legal','Agreement clause','The tenant may terminate the agreement on 30 days’ written notice, except during the initial 6-month term. The deposit must be returned within 14 days, subject to documented deductions.',
 {'zh-Hans':('承租人可提前 30 天发出书面通知终止协议，但最初 6 个月的期限除外。押金须在 14 天内退还，但可扣除有书面凭据的款项。','最初 6 个月内，承租人不能依此条款提前 30 天通知终止协议；在此期限之外，可提前 30 天发出书面通知终止协议。押金应在 14 天内退还，如有扣款，须有书面凭据。'),
 'es':('El arrendatario podrá resolver el acuerdo mediante aviso escrito con 30 días de antelación, salvo durante el plazo inicial de 6 meses. El depósito deberá devolverse en 14 días, con sujeción a deducciones documentadas.','Durante los primeros 6 meses no se aplica esta opción de resolución. Después, el arrendatario puede terminar el acuerdo avisando por escrito con 30 días de antelación. El depósito debe devolverse en 14 días y solo está sujeto a deducciones documentadas.')}),
('finance','Operating report','Revenue was EUR 1.20 million in 2025, excluding discontinued operations. The operating margin fell from 8.0% to 6.5%; this is a decline of 1.5 percentage points, not 1.5%.',
 {'zh-Hans':('2025 年收入为 EUR 1.20 百万，不包括终止经营业务。营业利润率从 8.0% 降至 6.5%；这表示下降 1.5 个百分点，而非下降 1.5%。','剔除终止经营业务后，2025 年收入为 EUR 1.20 百万。营业利润率由 8.0% 变为 6.5%，两者相差 1.5 个百分点；不能将这一差额写成下降 1.5%。'),
 'fr':('Le chiffre d’affaires s’est établi à EUR 1.20 million en 2025, hors activités abandonnées. La marge opérationnelle est passée de 8.0% à 6.5%, soit une baisse de 1.5 point de pourcentage, et non de 1.5%.','En excluant les activités abandonnées, le chiffre d’affaires de 2025 est de EUR 1.20 million. La marge opérationnelle recule de 8.0% à 6.5% : l’écart est de 1.5 point de pourcentage, ce qui ne signifie pas une baisse de 1.5%.')}),
('literary','Short fiction','At dusk, Mira closed the blue gate. “Tomorrow,” she said, though the train would not return for a week.',
 {'zh-Hans':('黄昏时，米拉关上了那扇蓝色的门。“明天。”她说，尽管火车要过一周才会回来。','暮色降临，米拉掩上蓝色的门。“明天。”她说。可火车再回来，已是一周以后。'),
 'ja':('夕暮れに、ミラは青い門を閉めた。「明日」と彼女は言ったが、列車が戻るのは一週間後だった。','夕暮れ、ミラは青い門を閉じた。「明日」。そう口にしたものの、次に列車が帰ってくるのは一週間も先だった。')}),
('public-service','Service notice','Applications received by 17:00 on 12 May will be reviewed in June. Late applications are not automatically rejected; they are considered only if places remain.',
 {'zh-Hans':('5 月 12 日 17:00 前收到的申请将在 6 月审核。逾期申请不会自动被拒绝；只有仍有名额时才予考虑。','在 5 月 12 日 17:00 前收到的申请，会进入 6 月的审核。晚到的申请并非一律拒绝，但只有名额未满时才会被考虑。'),
 'ar':('ستُراجع في يونيو الطلبات المستلمة بحلول الساعة 17:00 يوم 12 مايو. ولا تُرفض الطلبات المتأخرة تلقائياً؛ بل تُنظر فقط إذا بقيت أماكن.','إذا وصل الطلب بحلول الساعة 17:00 يوم 12 مايو، فستتم مراجعته في يونيو. أما الطلب المتأخر فلا يُرفض تلقائياً، لكن النظر فيه يتوقف على بقاء أماكن.')}),
('health','Information leaflet','Take 1 tablet with food once daily for 5 days, unless your clinician gives different instructions. Do not take a second dose to replace a missed dose.',
 {'zh-Hans':('每日随餐服用 1 片，连续服用 5 天，除非临床医生另有指示。不得为补服漏服剂量而再服一剂。','如果临床医生没有另作安排，应连续 5 天、每天随餐服用 1 片。漏服后，不得通过额外再服一剂来补偿。'),
 'es':('Tome 1 comprimido con comida una vez al día durante 5 días, salvo que su profesional clínico le indique otra cosa. No tome una segunda dosis para compensar una dosis olvidada.','Si su profesional clínico no ha dado instrucciones distintas, tome 1 comprimido al día con comida durante 5 días. Si olvida una dosis, no la compense tomando una segunda.')}),
('software','Protocol guide','Set timeout_ms to 1500. A value of 0 disables the timeout; it does not mean “retry immediately.” Preserve the identifier user_id in all examples.',
 {'zh-Hans':('将 timeout_ms 设为 1500。值为 0 时会禁用超时；它并不表示“立即重试”。所有示例中均应保留标识符 user_id。','将 timeout_ms 设置为 1500。如果设置为 0，含义是关闭超时，而不是立即重试。示例里的 user_id 是标识符，应保持原样。'),
 'fr':('Définissez timeout_ms sur 1500. La valeur 0 désactive le délai ; elle ne signifie pas « réessayer immédiatement ». Conservez l’identifiant user_id dans tous les exemples.','Utilisez 1500 pour timeout_ms. Si la valeur est 0, le délai est désactivé : cela ne demande pas de relancer immédiatement. Dans chaque exemple, user_id reste un identifiant inchangé.')})]

def main():
 global BASE
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument("--output-root",required=True);args=ap.parse_args();BASE=Path(args.output_root).resolve()
 BASE.mkdir(parents=True,exist_ok=True)
 # Five compact visual demos cover five target languages with paired text.
 chosen=[('zh-Hans','compact',1),('ja','compact',2),('ar','accessible',1),('es','editorial',1),('fr','compact',1)]
 for lang,style,columns in chosen:
  root=BASE/('demo-'+lang)
  if root.exists():
   import shutil;shutil.rmtree(root)
  import argparse
  t.init(argparse.Namespace(project=str(root),title={'zh-Hans':'多领域文档翻译示例','ja':'分野横断の翻訳例','ar':'نماذج ترجمة الوثائق','es':'Ejemplos de traducción documental','fr':'Exemples de traduction documentaire'}[lang],languages=lang,style=style,page_size='A4',columns=columns))
  r,m,c=t.project(root);m['author_credit']='Yufeng Zhan · Original demonstration text · MIT';source=r/'sources/original.txt';selected=[x for x in DATA if lang in x[3]];source.write_text('\n\n'.join(x[2] for x in selected));c['sources']=[{'id':'D001','name':'Author-owned synthetic examples','file':'sources/original.txt','sha256':t.sha(source),'media_type':'text/plain','page_count':None,'selection_scope':'all','rights':'Copyright 2026 Yufeng Zhan; MIT'}]
  for domain,title,en,tr in selected:
   headings={'zh-Hans':{'research':'研究记录','manual':'设备说明','legal':'协议条款','finance':'经营报告','literary':'短篇叙事','public-service':'公共服务公告','health':'信息单页','software':'协议指南'},'ja':{'research':'研究ノート','literary':'短い物語'},'ar':{'manual':'تعليمات الجهاز','public-service':'إعلان خدمة'},'es':{'legal':'Cláusula contractual','health':'Hoja informativa'},'fr':{'finance':'Rapport d’activité','software':'Guide du protocole'}}
   hb=t.add_block(c,'D001','heading',{'element':domain+'/heading'},[title],level=1);hb['units'][0]['translations'][lang]={'faithful':headings[lang][domain],'interpretive':headings[lang][domain]}
   b=t.add_block(c,'D001','paragraph',{'element':domain},[en]);u=b['units'][0];u['translations'][lang]={'faithful':tr[lang][0],'interpretive':tr[lang][1]}
  t.write(root/'project.json',m);t.write(root/'content.json',c)
  import publishing;publishing.build(root)
 # All cases are also distributed as editable author-owned data.
 t.write(BASE/'paired-cases.json',[{'domain':d,'title':title,'source':en,'translations':{l:{'faithful':v[0],'interpretive':v[1]} for l,v in tr.items()}} for d,title,en,tr in DATA])
 print('Created 5 demo projects and',len(DATA),'paired cross-domain cases')
if __name__=='__main__':main()
