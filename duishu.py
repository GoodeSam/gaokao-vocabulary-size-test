import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter
from scipy.interpolate import PchipInterpolator

# =========================
# 1) 全局样式设置
# =========================
plt.rcParams['font.sans-serif'] = [
    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
    'PingFang SC', 'WenQuanYi Zen Hei', 'Arial Unicode MS', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False

# 16:9 高清
fig, ax = plt.subplots(figsize=(16, 9), dpi=300)

# =========================
# 2) 构造平滑且严格命中锚点的曲线数据
#    - 显示仍为普通 x、对数 y 坐标
#    - 在 log(y) 空间使用 PCHIP 做单调三次插值
#    - 保证曲线光滑连续，且精确通过指定点
# =========================
anchors_x = np.array([1, 1000, 2000, 3000, 4484], dtype=float)
anchors_y = np.array([14102, 35, 13, 6, 2], dtype=float)

x = np.linspace(1, 4484, 4484)
interp = PchipInterpolator(anchors_x, np.log(anchors_y))
y = np.exp(interp(x))

# 强制指定点精确命中
exact_points = {
    1: 14102,
    1000: 35,
    2000: 13,
    3000: 6,
    4484: 2
}
for xi, yi in exact_points.items():
    idx = np.argmin(np.abs(x - xi))
    y[idx] = yi

# =========================
# 3) 设置 Y 轴为对数坐标
# =========================
ax.set_yscale('log')

# =========================
# 4) 区域高亮
# =========================
# 高频核心区：前500
ax.axvspan(1, 500, color='#2E8B57', alpha=0.14, zorder=0)

# 低频长尾区：后段
ax.axvspan(2700, 4484, color='#C0392B', alpha=0.10, zorder=0)
ax.text(
    3600, 5, '低频长尾区',
    ha='center', va='center',
    fontsize=16, color='#A93226',
    bbox=dict(boxstyle='round,pad=0.35', fc='white', ec='none', alpha=0.8),
    zorder=5
)

# =========================
# 5) 蓝色渐变填充（曲线下方）
#    对数坐标下，下边界不能为 0，因此取 1
# =========================
base_color = '#2F80ED'
n_layers = 100
y_base = np.ones_like(y)

ly_base = np.log(y_base)
ly = np.log(y)

for i in range(n_layers):
    frac1 = i / n_layers
    frac2 = (i + 1) / n_layers
    y1 = np.exp(ly_base + (ly - ly_base) * frac1)
    y2 = np.exp(ly_base + (ly - ly_base) * frac2)
    alpha = 0.01 + 0.20 * (frac2 ** 1.8)
    ax.fill_between(x, y1, y2, color=base_color, alpha=alpha, linewidth=0, zorder=1)

# 主曲线：平滑连续
ax.plot(x, y, color='#1565C0', linewidth=3.2, zorder=3)

# =========================
# 6) 精确绘制指定标注点
# =========================
points = [
    ("the", 1, 14102),
    ("black", 1000, 35),
    ("adaptation", 2000, 13),
    ("federal", 3000, 6),
]

px = [p[1] for p in points]
py = [p[2] for p in points]
ax.scatter(px, py, s=70, color='#0D47A1', edgecolor='white', linewidth=1.2, zorder=6)

# =========================
# 7) 标注（箭头精确指向点）
# =========================
annot_style = dict(
    arrowprops=dict(
        arrowstyle='->',
        color='#333333',
        lw=1.5,
        shrinkA=5,
        shrinkB=5,
        connectionstyle='arc3,rad=0.08'
    ),
    bbox=dict(boxstyle='round,pad=0.35', fc='white', ec='#D0D7DE', alpha=0.97),
    fontsize=13,
    color='#111111',
    zorder=10
)

ax.annotate(
    'the（第1位，14102次）',
    xy=(1, 14102),
    xytext=(500, 11000),
    ha='left', va='center',
    **annot_style
)

ax.annotate(
    'black（第1000位，35次）',
    xy=(1000, 35),
    xytext=(1300, 130),
    ha='left', va='center',
    **annot_style
)

ax.annotate(
    'adaptation（第2000位，13次）',
    xy=(2000, 13),
    xytext=(2250, 35),
    ha='left', va='center',
    **annot_style
)

ax.annotate(
    'federal（第3000位，6次）',
    xy=(3000, 6),
    xytext=(3200, 14),
    ha='left', va='center',
    **annot_style
)

# =========================
# 8) 坐标轴、刻度、网格
# =========================
ax.set_xlim(1, 4484)
ax.set_ylim(1, 20000)

ax.set_xlabel('频率排名', fontsize=16, labelpad=14)
ax.set_ylabel('出现次数（对数坐标）', fontsize=16, labelpad=14)
ax.set_title('齐普夫法则：高考真题词频分布', fontsize=24, pad=22, weight='bold')

# X 轴刻度
ax.set_xticks([1, 1000, 2000, 3000, 4000, 4484])
ax.set_xticklabels(['1', '1000', '2000', '3000', '4000', '4484'], fontsize=13)

# Y 轴刻度
yticks = [1, 10, 100, 1000, 10000]
ax.set_yticks(yticks)
ax.set_yticklabels([str(v) for v in yticks], fontsize=13)

# 关闭次刻度标签
ax.yaxis.set_minor_formatter(NullFormatter())

# 网格线
ax.grid(axis='y', which='major', linestyle='--', linewidth=0.8, alpha=0.35)
ax.grid(axis='x', linestyle=':', linewidth=0.5, alpha=0.15)

# 弱化上右边框
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# =========================
# 9) 辅助说明文字
# =========================
ax.text(
    620, 3500,
    '少量高频词覆盖大量出题',
    fontsize=14, color='#1E6B43',
    bbox=dict(boxstyle='round,pad=0.28', fc='white', ec='none', alpha=0.75),
    zorder=5
)

ax.text(
    2850, 1.5,
    '大量低频词仅零星出现',
    fontsize=14, color='#A93226',
    bbox=dict(boxstyle='round,pad=0.28', fc='white', ec='none', alpha=0.75),
    zorder=5
)

# =========================
# 10) 布局与导出
# =========================
plt.tight_layout()

# 导出高清 PNG
plt.savefig('zipf_gaokao_wordfreq_logy_smooth_16_9.png', dpi=300, bbox_inches='tight')

# 导出 SVG
plt.savefig('zipf_gaokao_wordfreq_logy_smooth_16_9.svg', bbox_inches='tight')

plt.show()
