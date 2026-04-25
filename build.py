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
    word, phon, cn, freq, files, _flag, _top_forms = r  # last two cols intentionally unused
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

# Tier thresholds — computed per-corpus by quantile so gaokao's long C tail
# doesn't balloon past zhongkao's 40% cap. Target: S≈10%, A≈20%, B≈30%, C≈40%.
# (Zhongkao's hardcoded 0.59/0.33/0.17 cutoffs produce S:277 A:644 B:1249 C:2314
#  on the 4484-word gaokao corpus — 52% C — which inflated vocab estimates.)
imps_desc = sorted((r['imp'] for r in rows), reverse=True)
N_rows = len(imps_desc)
S_CUT = imps_desc[int(0.10 * N_rows)]
A_CUT = imps_desc[int(0.30 * N_rows)]
B_CUT = imps_desc[int(0.60 * N_rows)]
print(f'Quantile-based tier cutoffs: S>={S_CUT:.4f} A>={A_CUT:.4f} B>={B_CUT:.4f}')

def assign_tier(imp):
    if imp >= S_CUT:
        return 'S'
    if imp >= A_CUT:
        return 'A'
    if imp >= B_CUT:
        return 'B'
    return 'C'

for r in rows:
    r['tier'] = assign_tier(r['imp'])

from collections import Counter
tier_ct = Counter(r['tier'] for r in rows)
print('Tier distribution:', dict(tier_ct))

# Sanity: ties at quantile boundaries can drift tier sizes; alert if it gets bad.
_TARGET_PCT = {'S': 10, 'A': 20, 'B': 30, 'C': 40}
for _t, _target in _TARGET_PCT.items():
    _actual = tier_ct[_t] / N_rows * 100
    assert abs(_actual - _target) <= 5, f'Tier {_t} drifted: {_actual:.1f}% vs target {_target}% (>5pp)'

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

# ---------- Step 11b: vocab-estimate algorithm fixes (gaokao-specific) ----------
# Background: the gaokao corpus has a much larger C tier (~40% of 4484 words vs
# zhongkao's ~40% of 3098). The inherited linear-extrapolation estimator
# (tierRate * tier.length) inflated results because:
#   (a) SKIP_TOP=40 assumed-mastered was too generous for gaokao-level students;
#   (b) genRound2's `alloc[t]||2` short-circuited the intended 0-allocation into 2,
#       silently oversampling the wrong tier and throwing off the total question budget;
#   (c) with only 1-2 C-tier samples, a single correct answer extrapolated to ~1800
#       "mastered" C words, flooding the estimate.
# Fixes applied here:
#   (a) SKIP_TOP 40 -> 25
#   (b) alloc[t]||2 -> alloc[t]??0
#   (c) Bayesian shrinkage + tiny-n cap on C contribution

# 11b.i: SKIP_TOP
assert 'const SKIP_TOP=40;' in html, 'SKIP_TOP constant not found'
html = html.replace('const SKIP_TOP=40;', 'const SKIP_TOP=25;')

# 11b.ii: alloc fallback bug (|| vs ??)
old_alloc = 'for(const w of pick(pool,alloc[t]||2)) qs.push(makeQ(w,2));'
new_alloc = 'for(const w of pick(pool,alloc[t]??0)) qs.push(makeQ(w,2));'
assert old_alloc in html, 'genRound2 alloc line not found'
html = html.replace(old_alloc, new_alloc)

# 11b.iii: estM loop — Bayesian shrinkage (K=2, P0=0.3) + C cap when n<2
old_estM = (
    '  // Estimated mastered words per tier (skipped top words count as mastered)\n'
    '  const estM={};let totalM=SKIP_TOP;\n'
    "  for(const t of['S','A','B','C']){\n"
    '    estM[t]=Math.max(0,Math.round(byTier[t].length*Math.max(0,tierRates[t])));\n'
    '    totalM+=estM[t];\n'
    '  }'
)
new_estM = (
    '  // Estimated mastered words per tier (skipped top words count as mastered).\n'
    '  // Bayesian shrinkage r\' = (K*P0 + n*r)/(K+n) pulls small-sample tier rates\n'
    '  // toward a mild prior so a lucky 1-of-1 on a big tier (especially C, ~1800 words)\n'
    '  // cannot extrapolate into a massive inflated estimate. The extra cap on tier C\n'
    '  // when n<2 protects against the worst single-sample pathological case.\n'
    '  const K_SHRINK=1,P0=0.3,C_CAP_LOW_N=1100;\n'
    '  const estM={};let totalM=SKIP_TOP;\n'
    "  for(const t of['S','A','B','C']){\n"
    '    const n=tierCounts[t];\n'
    '    const r=Math.max(0,tierRates[t]);\n'
    '    const rShrunk=(K_SHRINK*P0+n*r)/(K_SHRINK+n);\n'
    '    estM[t]=Math.max(0,Math.round(byTier[t].length*rShrunk));\n'
    "    if(t==='C'&&n<2) estM[t]=Math.min(estM[t],C_CAP_LOW_N);\n"
    '    totalM+=estM[t];\n'
    '  }'
)
assert old_estM in html, 'estM loop not found'
html = html.replace(old_estM, new_estM)

# 11b.iv: wrongS filter bug — `used` is built from Q.ans, so the `!used.has(...)`
# check on words pulled FROM Q.ans is always false. The intended round-1 S-tier
# re-test never ran. Drop the redundant filter.
old_wrongS = (
    '  // Extra confirmation for wrong S-tier words from round 1 (these are current-session, allow re-test)\n'
    "  const wrongS=Q.ans.filter(a=>a.tier==='S'&&a.score<0.5&&!used.has(a.word.w));\n"
    '  for(const a of wrongS.slice(0,2)){\n'
    '    if(!used.has(a.word.w)) qs.push(makeQ(a.word,2));\n'
    '  }'
)
new_wrongS = (
    '  // Extra confirmation for wrong S-tier words from round 1 (re-test current-session words).\n'
    "  // wrongS items come FROM Q.ans/`used`, so the legacy `!used.has(...)` filter would have made\n"
    '  // both the candidate selection and the dedup check always false — disabling the re-test entirely.\n'
    "  const wrongS=Q.ans.filter(a=>a.tier==='S'&&a.score<0.5);\n"
    '  for(const a of wrongS.slice(0,2)){\n'
    '    qs.push(makeQ(a.word,2));\n'
    '  }'
)
assert old_wrongS in html, 'wrongS block not found'
html = html.replace(old_wrongS, new_wrongS)

# 11b.v: choose() and handleTimeout() re-entry lock — without it, a fast double-click
# (or a click that races with the timeout firing) records two answers for the same
# question and advances the test pointer twice.
old_choose = (
    'function choose(idx){\n'
    '  // idx=-1 means "我不确定"\n'
    '  const elapsed=stopQTimer();\n'
    '  recordAnswer(idx,elapsed,false);\n'
    '  showFeedback(idx,false);\n'
    '}'
)
new_choose = (
    'function choose(idx){\n'
    '  // idx=-1 means "我不确定"\n'
    '  if(Q.locked) return;\n'
    '  Q.locked=true;\n'
    '  const elapsed=stopQTimer();\n'
    '  recordAnswer(idx,elapsed,false);\n'
    '  showFeedback(idx,false);\n'
    '}'
)
assert old_choose in html, 'choose() function not found'
html = html.replace(old_choose, new_choose)

old_timeout = (
    'function handleTimeout(){\n'
    '  // Auto-select "我不确定" (timeout)\n'
    '  const elapsed=stopQTimer();\n'
    '  recordAnswer(-1,elapsed,true);\n'
    '  showFeedback(-1,true);\n'
    '}'
)
new_timeout = (
    'function handleTimeout(){\n'
    '  // Auto-select "我不确定" (timeout)\n'
    '  if(Q.locked) return;\n'
    '  Q.locked=true;\n'
    '  const elapsed=stopQTimer();\n'
    '  recordAnswer(-1,elapsed,true);\n'
    '  showFeedback(-1,true);\n'
    '}'
)
assert old_timeout in html, 'handleTimeout() function not found'
html = html.replace(old_timeout, new_timeout)

# Reset the lock when the next question is shown.
old_showq_head = (
    'function showQ(){\n'
    '  const q=Q.qs[Q.cur];if(!q)return;\n'
    '  const total=Q.qs.length;'
)
new_showq_head = (
    'function showQ(){\n'
    '  const q=Q.qs[Q.cur];if(!q)return;\n'
    '  Q.locked=false;\n'
    '  const total=Q.qs.length;'
)
assert old_showq_head in html, 'showQ() head not found'
html = html.replace(old_showq_head, new_showq_head)

# 11b.vi: switch from TEST MODE (15 Qs) to production allocations (35 Qs total
# = 14+14+7). The UI already advertises 14/14/7 to users, so this also fixes a
# visible inconsistency. More samples per tier also lets the Bayesian shrinkage
# converge closer to true rates, reducing residual estimation error.
old_round1 = (
    '  // TEST MODE: 6 questions (normally 14: 4S,4A,3B,3C)\n'
    '  const alloc={S:2,A:2,B:1,C:1};'
)
new_round1 = (
    '  // 14 questions: broad scan across all tiers (4S, 4A, 3B, 3C).\n'
    '  const alloc={S:4,A:4,B:3,C:3};'
)
assert old_round1 in html, 'genRound1 alloc not found'
html = html.replace(old_round1, new_round1)

old_round2 = (
    '  // TEST MODE: 6 questions (normally 14: 6,4,3,1)\n'
    '  const alloc={[ranked[0]]:3,[ranked[1]]:2,[ranked[2]]:1,[ranked[3]]:0};'
)
new_round2 = (
    '  // 14 questions weighted by rate-to-0.55 closeness (focus probe: 6,4,3,1).\n'
    '  const alloc={[ranked[0]]:6,[ranked[1]]:4,[ranked[2]]:3,[ranked[3]]:1};'
)
assert old_round2 in html, 'genRound2 alloc not found'
html = html.replace(old_round2, new_round2)

old_round3 = (
    '  // TEST MODE: 3 questions (normally 7)\n'
    '  const qs=[];let rem=3;'
)
new_round3 = (
    '  // 7 questions targeting weak tiers from rounds 1-2 (gap confirmation).\n'
    '  const qs=[];let rem=7;'
)
assert old_round3 in html, 'genRound3 rem not found'
html = html.replace(old_round3, new_round3)

# 11b.vii: R2 budget reservation — without it, the wrongS re-test items pushed at the
# bottom of genRound2 inflate the round past 14 questions (and the total past 35).
# This replacement runs AFTER 11b.iv (wrongS bug fix) and 11b.vi (R2 alloc bump),
# so it matches the post-fix text. Reserve up to 2 slots for re-tests by deducting
# from the highest-allocated tier so the round still totals 14.
old_r2_budget = (
    '  const alloc={[ranked[0]]:6,[ranked[1]]:4,[ranked[2]]:3,[ranked[3]]:1};\n'
    '  const used=new Set(Q.ans.map(a=>a.word.w));\n'
    '  const excl=w=>used.has(w.w)||_historyWords.has(w.w);\n'
    '  const qs=[];\n'
    "  for(const t of['S','A','B','C']){\n"
    '    const pool=byTier[t].filter(w=>w.cn&&!excl(w));\n'
    '    for(const w of pick(pool,alloc[t]??0)) qs.push(makeQ(w,2));\n'
    '  }\n'
    '  // Extra confirmation for wrong S-tier words from round 1 (re-test current-session words).\n'
    "  // wrongS items come FROM Q.ans/`used`, so the legacy `!used.has(...)` filter would have made\n"
    '  // both the candidate selection and the dedup check always false — disabling the re-test entirely.\n'
    "  const wrongS=Q.ans.filter(a=>a.tier==='S'&&a.score<0.5);\n"
    '  for(const a of wrongS.slice(0,2)){\n'
    '    qs.push(makeQ(a.word,2));\n'
    '  }'
)
new_r2_budget = (
    '  const alloc={[ranked[0]]:6,[ranked[1]]:4,[ranked[2]]:3,[ranked[3]]:1};\n'
    '  // Reserve up to 2 slots for re-testing wrong S-tier words from round 1 by\n'
    '  // deducting from the highest-allocated tier; the round still totals 14 questions.\n'
    "  const wrongS=Q.ans.filter(a=>a.tier==='S'&&a.score<0.5).slice(0,2);\n"
    '  alloc[ranked[0]]=Math.max(0,alloc[ranked[0]]-wrongS.length);\n'
    '  const used=new Set(Q.ans.map(a=>a.word.w));\n'
    '  const excl=w=>used.has(w.w)||_historyWords.has(w.w);\n'
    '  const qs=[];\n'
    "  for(const t of['S','A','B','C']){\n"
    '    const pool=byTier[t].filter(w=>w.cn&&!excl(w));\n'
    '    for(const w of pick(pool,alloc[t]??0)) qs.push(makeQ(w,2));\n'
    '  }\n'
    '  for(const a of wrongS){\n'
    '    qs.push(makeQ(a.word,2));\n'
    '  }'
)
assert old_r2_budget in html, 'genRound2 post-fix block not found (R2 budget reservation)'
html = html.replace(old_r2_budget, new_r2_budget)

# 11b.viii: studyStartRank misses SKIP_TOP — totalM includes SKIP_TOP, so the
# study-start rank advice was offset 25 words too early.
assert '  let studyStartRank=0;' in html, 'studyStartRank initializer not found'
html = html.replace('  let studyStartRank=0;', '  let studyStartRank=SKIP_TOP;')

# 11b.ix: coverage uses raw tierRates which can be negative (wrong=-0.3). estM clamps
# to non-negative; coverage should too, otherwise scoring behavior is inconsistent.
old_cov = "  for(const t of['S','A','B','C']) covFreq+=tierRates[t]*tierFreq[t];"
new_cov = "  for(const t of['S','A','B','C']) covFreq+=Math.max(0,tierRates[t])*tierFreq[t];"
assert old_cov in html, 'coverage loop not found'
html = html.replace(old_cov, new_cov)

# 11b.x: startWord and nearbyWords are computed but never read anywhere in the
# rendered report — pure dead code from an unfinished feature.
old_dead = (
    '  // The word at that rank\n'
    '  const startWord=studyStartRank>0&&studyStartRank<=WORDS.length?WORDS[studyStartRank-1]:null;\n'
    '  // Also find a few words around that position for context\n'
    '  const nearbyWords=WORDS.slice(Math.max(0,studyStartRank-3),Math.min(WORDS.length,studyStartRank+7));\n'
    '\n'
)
assert old_dead in html, 'studyStart dead-code block not found'
html = html.replace(old_dead, '')

# 11b.xi: showAll() tries to remove `.show-all-btn` but the button has no such
# class — the cleanup branch never executes. Add the class so it works.
old_btn = (
    '<button class="btn btn-o" style="width:auto;padding:6px 16px;font-size:12px"\n'
    '        onclick="showAll()">'
)
new_btn = (
    '<button class="btn btn-o show-all-btn" style="width:auto;padding:6px 16px;font-size:12px"\n'
    '        onclick="showAll()">'
)
assert old_btn in html, 'show-all button markup not found'
html = html.replace(old_btn, new_btn)

# 11b.xii: extract TIERS constant. Done LAST so prior text replacements still match
# the legacy ['S','A','B','C'] literal. Patches must run in order:
#   1) .sort() — mutating, replace with [...TIERS].sort() to avoid clobbering
#   2) `of['S','A','B','C']` → `of TIERS` (note added space — original had `of[`)
#   3) `${['S','A','B','C'].map(` → `${TIERS.map(`
#   4) Insert the const TIERS declaration AFTER the wholesale replace, so the
#      replacement doesn't recurse into the literal inside the const itself.
old_sort = "const ranked=['S','A','B','C'].sort("
new_sort = 'const ranked=[...TIERS].sort('
assert old_sort in html, 'ranked.sort line not found'
html = html.replace(old_sort, new_sort)

_n_of = html.count("of['S','A','B','C']")
html = html.replace("of['S','A','B','C']", 'of TIERS')
_n_map = html.count("['S','A','B','C'].map(")
html = html.replace("['S','A','B','C'].map(", 'TIERS.map(')
assert "['S','A','B','C']" not in html, 'Unexpected residual tier literal'

html = html.replace(
    'const SKIP_TOP=25;',
    "const TIERS=Object.freeze(['S','A','B','C']);\nconst SKIP_TOP=25;",
)
print(f'Replaced {_n_of + _n_map + 1} legacy tier-array literals with TIERS constant')

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
