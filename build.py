"""
Build high-school (高考) vocabulary test index.html based on zhongkao reference template.

Reads:
  - /Users/victor/projects/高考词汇量测试/土妹高考词汇4509-20260304版.xlsx  (source data)
  - /Users/victor/projects/中考词汇量测试/index.html                         (template)

Writes:
  - /Users/victor/projects/高考词汇量测试/index.html
  - /Users/victor/projects/高考词汇量测试/words_data.json (reference export)
"""
import json
import math
import re
import openpyxl

SRC_XLSX = '/Users/victor/projects/高考词汇量测试/土妹高考词汇4509-20260304版.xlsx'
TEMPLATE_HTML = '/Users/victor/projects/中考词汇量测试/index.html'
OUT_HTML = '/Users/victor/projects/高考词汇量测试/index.html'
OUT_JSON = '/Users/victor/projects/高考词汇量测试/words_data.json'

# ---------- Step 1: parse xlsx ----------
wb = openpyxl.load_workbook(SRC_XLSX, data_only=True)
ws = wb['Sheet']

rows = []
for r in ws.iter_rows(min_row=3, values_only=True):
    word, phon, cn, freq, files, flag, top_forms = r
    if not word or not cn or not freq or not files:
        continue
    word = str(word).strip()
    phon = str(phon).strip() if phon else ''
    cn = str(cn).strip()
    freq = int(freq)
    files = int(files)
    rows.append({'w': word, 'p': phon, 'cn': cn, 'freq': freq, 'files': files})

# Sort by freq desc (primary), files desc (secondary)
rows.sort(key=lambda x: (-x['freq'], -x['files']))

# Dedup by lowercased word (keep first — highest freq)
seen = set()
dedup = []
for r in rows:
    key = r['w'].lower()
    if key in seen:
        continue
    seen.add(key)
    dedup.append(r)
rows = dedup

max_freq = max(r['freq'] for r in rows)
max_files = max(r['files'] for r in rows)
print(f'Total words: {len(rows)}  max_freq={max_freq}  max_files={max_files}')

# ---------- Step 2: compute importance and tier ----------
# Same formula as zhongkao: imp = 0.5 * log(freq)/log(max_freq) + 0.5 * files/max_files
log_max = math.log(max_freq)
for r in rows:
    imp = 0.5 * math.log(r['freq']) / log_max + 0.5 * r['files'] / max_files
    r['imp'] = round(imp, 4)

# Tier thresholds — match zhongkao cutoffs
def assign_tier(imp):
    if imp >= 0.59:
        return 'S'
    if imp >= 0.33:
        return 'A'
    if imp >= 0.17:
        return 'B'
    return 'C'

for r in rows:
    r['tier'] = assign_tier(r['imp'])

from collections import Counter
tier_ct = Counter(r['tier'] for r in rows)
print('Tier distribution:', dict(tier_ct))

# Report Zipf anchor samples at ranks 1, 1000, 2000, 3000, 4000
anchors = {}
for rank in (1, 1000, 2000, 3000, 4000):
    if rank <= len(rows):
        r = rows[rank - 1]
        anchors[rank] = (r['w'], r['freq'])
print('Zipf anchors:', anchors)

# ---------- Step 3: build W array JS literal ----------
def js_str(s):
    # JSON string escaping works fine for JS string literals
    return json.dumps(s, ensure_ascii=False)

w_items = []
for r in rows:
    w_items.append(
        f"[{js_str(r['w'])},{js_str(r['p'])},{js_str(r['cn'])},{r['freq']},{r['files']},{r['imp']},\"{r['tier']}\"]"
    )
W_JS = 'const W=[' + ','.join(w_items) + '];'

# ---------- Step 4: export JSON (for reference) ----------
with open(OUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=None)

# ---------- Step 5: load template ----------
with open(TEMPLATE_HTML, 'r', encoding='utf-8') as f:
    html = f.read()

# ---------- Step 6: replace W=[...] ----------
# Template has: const W=[...];\n// W[i] = [...]
# The W= line is massive; we match greedily from 'const W=[' up through the closing '];' on the same line.
m = re.search(r"const W=\[.*?\];\n", html, flags=re.DOTALL)
assert m, 'W array block not found in template'
html = html[:m.start()] + W_JS + '\n' + html[m.end():]

# ---------- Step 7: strip large base64 images (keep template lean) ----------
# There are two <img src="data:image/webp;base64,..."> instances in the welcome cards.
# Replace each with a clean placeholder block.
html, n_imgs = re.subn(
    r'<div style="display:flex;justify-content:center;margin:12px 0"><img src="data:image/webp;base64,[^"]+"[^>]*></div>',
    '',
    html
)
print(f'Stripped {n_imgs} inline Zipf image(s).')

# ---------- Step 8: text replacements ----------
replacements = [
    # Page chrome
    ('你的中考词汇够用吗？', '你的高考词汇够用吗？'),
    ('142套中考真题告诉你答案', '84套高考真题告诉你答案'),
    ('中考词汇智能诊断', '高考词汇智能诊断'),
    ('<title>中考词汇智能诊断</title>', '<title>高考词汇智能诊断</title>'),
    ('为什么这个测试和你的中考成绩直接相关？', '为什么这个测试和你的高考成绩直接相关？'),

    # Welcome body copy
    ('我们对 <b>142 份全国中考真题</b>进行了词频统计',
     '我们对 <b>84 份全国高考真题</b>进行了词频统计'),
    ('教材和课标中的单词与中考真题', '教材和课标中的单词与高考真题'),
    ('<b>尽可能多地掌握中考真题中的高频词汇</b>',
     '<b>尽可能多地掌握高考真题中的高频词汇</b>'),

    # Stats blocks
    ('<div class="n">3098</div><div class="l">中考词汇总量</div>',
     f'<div class="n">{len(rows)}</div><div class="l">高考词汇总量</div>'),
    ('<div class="n">142</div><div class="l">真题试卷来源</div>',
     '<div class="n">84</div><div class="l">真题试卷来源</div>'),

    # Footer (template string already had 中考词汇智能诊断 which was swapped, so match the partially-swapped form)
    ('<div class="footer">高考词汇智能诊断 &middot; 142套全国中考真题 &middot; 3098词</div>',
     f'<div class="footer">高考词汇智能诊断 &middot; 84套全国高考真题 &middot; {len(rows)}词\n'
     f'    <div style="margin-top:6px"><a href="https://goodesam.github.io/zhongkao-vocabulary-size-test/" style="color:var(--primary);text-decoration:none">中考词汇诊断</a></div>\n'
     f'  </div>'),

    # Reports / CTA copy
    ('// ══════ 4. 中考题型风险卡 ══════', '// ══════ 4. 高考题型风险卡 ══════'),
    ('中考题型风险预测', '高考题型风险预测'),
    ('中考提分效用', '高考提分效用'),
    ('// (too expensive to do full N^2 on 3098 words at runtime, so we use heuristics)',
     f'// (too expensive to do full N^2 on {len(rows)} words at runtime, so we use heuristics)'),
    ("const reason3='基于142套真题词频数据定制学习路径，避免\"背过的没考、要考的没背\"';",
     "const reason3='基于84套真题词频数据定制学习路径，避免\"背过的没考、要考的没背\"';"),
    ('若不进行针对性训练，预估各题型词汇相关得分率',
     '若不进行针对性训练，预估各题型词汇相关得分率'),
    ('样本覆盖142套中考真题', '样本覆盖84套高考真题'),
    ('本测试基于中考词库（共 3098 词）',
     f'本测试基于高考词库（共 {len(rows)} 词）'),
    ('你的中考词汇已基本过关，请联系土妹参加<b style="color:#7c3aed">高中词汇专项测试</b>',
     '你的高考词汇已基本过关，请联系土妹参加<b style="color:#7c3aed">四六级/考研词汇专项测试</b>'),
    ('#中考词汇挑战', '#高考词汇挑战'),
    ('扫码测测你的中考词汇量', '扫码测测你的高考词汇量'),
    ('中考词汇测试-邀请好友.png', '高考词汇测试-邀请好友.png'),
    ('中考词汇智能诊断报告', '高考词汇智能诊断报告'),
    ('基于142套全国中考真题词频数据', '基于84套全国高考真题词频数据'),
    ('中考词汇诊断报告.png', '高考词汇诊断报告.png'),
    ('<b>数据来源</b>：142 份全国各省中考真题，提取 3098 个考试词汇及词频',
     f'<b>数据来源</b>：84 份全国各省高考真题，提取 {len(rows)} 个考试词汇及词频'),

    # Constants
    ('const TOTAL_FILES=142;', 'const TOTAL_FILES=84;'),

    # Zipf anchor inline stats (update words and counts)
    (
        '排名第 1 的单词 <b>the</b> 出现了 <b style="color:var(--primary)">22,828</b> 次<br>\n'
        '          排名第 1,000 的单词 <b>shake</b> 出现了 <b>55</b> 次<br>\n'
        '          排名第 2,000 的单词 <b>greenhouse</b> 只出现了 <b>12</b> 次<br>\n'
        '          排名第 3,000 的单词 <b>virtual</b> 仅出现了 <b>2</b> 次',
        (
            f'排名第 1 的单词 <b>{anchors.get(1,("-",0))[0]}</b> 出现了 '
            f'<b style="color:var(--primary)">{anchors.get(1,("-",0))[1]:,}</b> 次<br>\n'
            f'          排名第 1,000 的单词 <b>{anchors.get(1000,("-",0))[0]}</b> 出现了 '
            f'<b>{anchors.get(1000,("-",0))[1]}</b> 次<br>\n'
            f'          排名第 2,000 的单词 <b>{anchors.get(2000,("-",0))[0]}</b> 只出现了 '
            f'<b>{anchors.get(2000,("-",0))[1]}</b> 次<br>\n'
            f'          排名第 3,000 的单词 <b>{anchors.get(3000,("-",0))[0]}</b> 仅出现了 '
            f'<b>{anchors.get(3000,("-",0))[1]}</b> 次'
        ),
    ),
]

for old, new in replacements:
    if old not in html:
        print(f'WARN: replacement not found → {old[:80]!r}')
        continue
    html = html.replace(old, new)

# Fix orphan references to the Zipf images (we removed the pictures above).
orphan_pattern = (
    '<p style="margin-bottom:8px">上图由于对 Y 轴采用了对数坐标系，并不能准确地反映词频的真实状态。'
    '如果采用普通坐标系，单词词频分布是下图：</p>'
)
orphan_replace = (
    '<p style="margin-bottom:8px">词频分布高度倾斜：前 500 个高频词在真题中反复出现，'
    '而后段数千个低频词整体只零星出现几次。</p>'
)
if orphan_pattern in html:
    html = html.replace(orphan_pattern, orphan_replace)

# ---------- Step 9: replace vocabToGrade thresholds (gaokao-oriented) ----------
# Old (zhongkao): upper bound at ~3500. We stretch the ceiling to the gaokao corpus size.
old_grade_fn = (
    'function vocabToGrade(n){\n'
    "    if(n>=3500)return'高中3年级';if(n>=2800)return'高中2年级';if(n>=2400)return'高中1年级';\n"
    "    if(n>=1800)return'初中3年级';if(n>=1300)return'初中2年级';if(n>=900)return'初中1年级';\n"
    "    if(n>=700)return'小学6年级';if(n>=500)return'小学5年级';if(n>=350)return'小学4年级';\n"
    "    if(n>=250)return'小学3年级';if(n>=150)return'小学2年级';return'小学1年级';\n"
    '  }'
)
new_grade_fn = (
    'function vocabToGrade(n){\n'
    "    if(n>=4200)return'高中3年级';if(n>=3600)return'高中2年级';if(n>=2900)return'高中1年级';\n"
    "    if(n>=2200)return'初中3年级';if(n>=1600)return'初中2年级';if(n>=1100)return'初中1年级';\n"
    "    if(n>=800)return'小学6年级';if(n>=550)return'小学5年级';if(n>=380)return'小学4年级';\n"
    "    if(n>=260)return'小学3年级';if(n>=160)return'小学2年级';return'小学1年级';\n"
    '  }'
)
assert old_grade_fn in html, 'vocabToGrade function not found'
html = html.replace(old_grade_fn, new_grade_fn)

# ---------- Step 10: update gradeVocab percentile reference (gaokao-oriented) ----------
old_vocab = (
    "const gradeVocab={'小学1年级':[80,40],'小学2年级':[180,60],'小学3年级':[350,90],"
    "'小学4年级':[550,120],'小学5年级':[750,150],'小学6年级':[950,180],"
    "'初中1年级':[1300,220],'初中2年级':[1700,260],'初中3年级':[2100,300],"
    "'高中1年级':[2600,350],'高中2年级':[3100,380],'高中3年级':[3600,400]};"
)
new_vocab = (
    "const gradeVocab={'小学1年级':[80,40],'小学2年级':[180,60],'小学3年级':[350,90],"
    "'小学4年级':[550,120],'小学5年级':[750,150],'小学6年级':[950,180],"
    "'初中1年级':[1300,220],'初中2年级':[1700,260],'初中3年级':[2100,300],"
    "'高中1年级':[2900,380],'高中2年级':[3600,420],'高中3年级':[4300,450]};"
)
assert old_vocab in html, 'gradeVocab literal not found'
html = html.replace(old_vocab, new_vocab)

# ---------- Step 11: update overflow tip threshold (2800 → ~4200) ----------
html = html.replace(
    'if(totalM>2800){',
    'if(totalM>4200){',
)

# ---------- Step 12: write output ----------
with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Wrote {OUT_HTML} ({len(html)/1024:.1f} KB)')
