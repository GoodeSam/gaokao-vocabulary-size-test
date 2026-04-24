"""
Build high-school (高考) vocabulary test index.html based on zhongkao reference template.

Reads:
  - /Users/victor/projects/高考词汇量测试/土妹高考词汇4509-20260304版.xlsx  (source data)
  - /Users/victor/projects/中考词汇量测试/index.html                         (template)

Writes:
  - /Users/victor/projects/高考词汇量测试/index.html
  - /Users/victor/projects/高考词汇量测试/words_data.json (reference export)
"""
import base64
import io
import json
import math
import re
import openpyxl
from PIL import Image

SRC_XLSX = '/Users/victor/projects/高考词汇量测试/土妹高考词汇4509-20260304版.xlsx'
TEMPLATE_HTML = '/Users/victor/projects/中考词汇量测试/index.html'
OUT_HTML = '/Users/victor/projects/高考词汇量测试/index.html'
OUT_JSON = '/Users/victor/projects/高考词汇量测试/words_data.json'

# Zipf charts (gaokao-specific). PNGs are pre-generated via duishu.py / test.py;
# this script compresses them to WebP in-memory and injects them into the
# template (replacing the zhongkao charts).
ZIPF_LOGY_PNG = '/Users/victor/projects/高考词汇量测试/zipf_gaokao_wordfreq_logy_smooth_16_9.png'
ZIPF_LINEAR_PNG = '/Users/victor/projects/高考词汇量测试/zipf_gaokao_wordfreq_smooth_9_16.png'
WEBP_QUALITY = 82

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

# ---------- Step 7: swap inline Zipf charts from zhongkao → gaokao ----------
# Template has two <img src="data:image/webp;base64,...">: first is the log-y 16:9
# chart, second is the linear 9:16 chart. Replace only the base64 payload so the
# surrounding sizing/CSS attrs are preserved exactly.
def _png_to_webp_b64(png_path, quality=WEBP_QUALITY):
    im = Image.open(png_path)
    buf = io.BytesIO()
    im.save(buf, 'WEBP', quality=quality, method=6)
    return base64.b64encode(buf.getvalue()).decode('ascii')

gaokao_charts_b64 = [_png_to_webp_b64(ZIPF_LOGY_PNG), _png_to_webp_b64(ZIPF_LINEAR_PNG)]
_chart_idx = [0]

def _swap_chart(m):
    i = _chart_idx[0]
    if i >= len(gaokao_charts_b64):
        return m.group(0)
    _chart_idx[0] += 1
    prefix, suffix = m.group(1), m.group(2)
    return f'{prefix}{gaokao_charts_b64[i]}{suffix}'

html, n_imgs = re.subn(
    r'(<img src="data:image/webp;base64,)[^"]+(")',
    _swap_chart,
    html,
)
print(f'Swapped {n_imgs} inline Zipf image(s) to gaokao charts.')
assert _chart_idx[0] == 2, f'expected 2 inline charts to swap, got {_chart_idx[0]}'

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

    # Footer: zhongkao template now already embeds a "→ 高考词汇诊断" button.
    # Swap stats (142→84, 3098→{len}) and flip the cross-link (→ zhongkao).
    (
        '<div class="footer">高考词汇智能诊断 &middot; 142套全国中考真题 &middot; 3098词\n'
        '    <div style="margin-top:14px"><a href="https://goodesam.github.io/gaokao-vocabulary-size-test/" style="display:inline-block;padding:10px 22px;background:linear-gradient(135deg,var(--primary),#7c3aed);color:#fff;font-size:15px;font-weight:800;text-decoration:none;border-radius:22px;box-shadow:0 4px 14px rgba(67,97,238,.35);letter-spacing:.5px">→ 高考词汇诊断</a></div>\n'
        '  </div>',
        f'<div class="footer">高考词汇智能诊断 &middot; 84套全国高考真题 &middot; {len(rows)}词\n'
        f'    <div style="margin-top:14px"><a href="https://goodesam.github.io/zhongkao-vocabulary-size-test/" style="display:inline-block;padding:10px 22px;background:linear-gradient(135deg,var(--primary),#7c3aed);color:#fff;font-size:15px;font-weight:800;text-decoration:none;border-radius:22px;box-shadow:0 4px 14px rgba(67,97,238,.35);letter-spacing:.5px">→ 中考词汇诊断</a></div>\n'
        f'  </div>'
    ),

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

# Report-page cross-link: zhongkao template already has a "→ 高考词汇诊断" button
# below the "再测一次" button. Flip it to point to zhongkao for the gaokao site.
restart_block_old = (
    '    <div class="txc mt14">\n'
    '      <button class="btn btn-o" style="width:100%" onclick="restart()">'
    '再测一次（换一批词）</button>\n'
    '      <div style="margin-top:14px"><a href="https://goodesam.github.io/gaokao-vocabulary-size-test/" '
    'style="display:inline-block;padding:12px 26px;background:linear-gradient(135deg,var(--primary),#7c3aed);'
    'color:#fff;font-size:16px;font-weight:800;text-decoration:none;border-radius:24px;'
    'box-shadow:0 4px 16px rgba(67,97,238,.4);letter-spacing:.5px">→ 高考词汇诊断</a></div>\n'
    '    </div>'
)
restart_block_new = (
    '    <div class="txc mt14">\n'
    '      <button class="btn btn-o" style="width:100%" onclick="restart()">'
    '再测一次（换一批词）</button>\n'
    '      <div style="margin-top:14px"><a href="https://goodesam.github.io/zhongkao-vocabulary-size-test/" '
    'style="display:inline-block;padding:12px 26px;background:linear-gradient(135deg,var(--primary),#7c3aed);'
    'color:#fff;font-size:16px;font-weight:800;text-decoration:none;border-radius:24px;'
    'box-shadow:0 4px 16px rgba(67,97,238,.4);letter-spacing:.5px">→ 中考词汇诊断</a></div>\n'
    '    </div>'
)
if restart_block_old in html:
    html = html.replace(restart_block_old, restart_block_new)
else:
    print('WARN: restart block not found — skipped re-targeting report-page link')

# ---------- Step 9: replace vocabToGrade thresholds ----------
# New mapping adds a top tier "大学四级" at ≥4200 (gaokao corpus ceiling is 4484),
# with lower tiers mirroring zhongkao thresholds.
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
    "    if(n>=4200)return'大学四级';if(n>=3500)return'高中3年级';if(n>=2800)return'高中2年级';\n"
    "    if(n>=2300)return'高中1年级';if(n>=1800)return'初中3年级';if(n>=1300)return'初中2年级';\n"
    "    if(n>=900)return'初中1年级';if(n>=700)return'小学6年级';if(n>=500)return'小学5年级';\n"
    "    if(n>=350)return'小学4年级';if(n>=250)return'小学3年级';if(n>=150)return'小学2年级';\n"
    "    return'小学1年级';\n"
    '  }'
)
assert old_grade_fn in html, 'vocabToGrade function not found'
html = html.replace(old_grade_fn, new_grade_fn)

# ---------- Step 10: extend gradeOrder to include 大学四级 ----------
# Needed so diff=eqIdx-curIdx still works when equivGrade resolves to 大学四级.
old_grade_order = (
    "const gradeOrder=['小学1年级','小学2年级','小学3年级','小学4年级','小学5年级',"
    "'小学6年级','初中1年级','初中2年级','初中3年级','高中1年级','高中2年级','高中3年级'];"
)
new_grade_order = (
    "const gradeOrder=['小学1年级','小学2年级','小学3年级','小学4年级','小学5年级',"
    "'小学6年级','初中1年级','初中2年级','初中3年级','高中1年级','高中2年级','高中3年级',"
    "'大学四级'];"
)
assert old_grade_order in html, 'gradeOrder array not found'
html = html.replace(old_grade_order, new_grade_order)

# ---------- Step 11: gradeVocab (z-score reference) stays aligned with thresholds ----------
# Thresholds now mirror zhongkao for 小学~高中, so zhongkao's gradeVocab is correct here;
# no replacement needed (the template already has these values).

# ---------- Step 12: overflow tip threshold ----------
# Keep at 4200 — warning is about test pool ceiling (4484 words) becoming unreliable,
# which conveniently aligns with the 大学四级 threshold.
html = html.replace(
    'if(totalM>2800){',
    'if(totalM>4200){',
)

# ---------- Step 12: write output ----------
with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Wrote {OUT_HTML} ({len(html)/1024:.1f} KB)')
