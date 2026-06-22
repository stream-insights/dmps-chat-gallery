#!/usr/bin/env python3
"""
YouTubeライブ配信のチャットを取得して分析レポート(HTML)を一発生成する。

使い方:
    python3 run_report.py "https://www.youtube.com/watch?v=XXXXXXXX"

必要なもの(初回のみ):
    python3 -m pip install --user yt-dlp janome

外部APIは使わない(yt-dlpがチャットリプレイを取得)。APIキー/クォータ不要。
"""
import sys, os, re, json, subprocess, tempfile, html as H
from collections import Counter
from datetime import datetime, timezone

# ---------- 0. 引数 ----------
if len(sys.argv) < 2:
    print("使い方: python3 run_report.py \"<YouTube URL>\" [カテゴリ]"); sys.exit(1)
URL = sys.argv[1]
m = re.search(r'(?:v=|youtu\.be/|/live/)([\w-]{11})', URL)
VID = m.group(1) if m else "video"

# ===== 配信シリーズ分類 =====
# (表示名, タイトルに含まれていたらそのシリーズと判定するキーワード群)
# 新しいシリーズが増えたらここに1行足すだけ。
SERIES_RULES = [
    ("デュエプレ魂",   ["デュエプレ魂", "デュエプレ!!魂", "デュエプレ！！魂"]),
    ("バトルアリーナ", ["バトルアリーナ"]),
]
def infer_category(title):
    for cat, kws in SERIES_RULES:
        if any(k in title for k in kws):
            return cat
    return "その他"

try:
    from janome.tokenizer import Tokenizer
except ImportError:
    print("janome が無い。 python3 -m pip install --user janome を実行してね"); sys.exit(1)

# ---------- 1. yt-dlpで取得 ----------
tmp = tempfile.mkdtemp()
base = os.path.join(tmp, VID)
print(f"[1/4] チャット取得中… ({VID})")
r = subprocess.run(
    [sys.executable, "-m", "yt_dlp", "--write-subs", "--sub-langs", "live_chat",
     "--skip-download", "--write-info-json", "-o", base + ".%(ext)s", URL],
    capture_output=True, text=True)
chat_path = base + ".live_chat.json"
info_path = base + ".info.json"
if not os.path.exists(chat_path):
    print("チャットが取得できなかった。配信にリプレイチャットが無いか、URLを確認。")
    print(r.stderr[-800:]); sys.exit(1)

title = VID
if os.path.exists(info_path):
    try: title = json.load(open(info_path, encoding="utf-8")).get("title", VID)
    except Exception: pass

# 第2引数で明示指定があればそれを、なければタイトルから自動判定
EXPLICIT_CAT = sys.argv[2].strip() if len(sys.argv) > 2 and sys.argv[2].strip() else None
CATEGORY = EXPLICIT_CAT or infer_category(title)

# ---------- 2. パース ----------
print("[2/4] パース中…")
rows = []
with open(chat_path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try: dd = json.loads(line)
        except json.JSONDecodeError: continue
        act = dd.get("replayChatItemAction", {})
        offset = int(act.get("videoOffsetTimeMsec", "0") or 0)
        for a in act.get("actions", []):
            item = a.get("addChatItemAction", {}).get("item", {})
            rr = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer")
            if not rr: continue
            parts = []
            for run in rr.get("message", {}).get("runs", []):
                if "text" in run: parts.append(run["text"])
                elif "emoji" in run:
                    sc = run["emoji"].get("shortcuts", [])
                    if sc: parts.append(sc[0])
            rows.append((offset, rr.get("authorName", {}).get("simpleText", ""), "".join(parts)))

if not rows:
    print("コメントが0件。"); sys.exit(1)

# ---------- 3. 分析 ----------
print(f"[3/4] 分析中… ({len(rows)}件)")
t = Tokenizer()
STOP = set('草 てる する ある いる なる これ それ あれ やつ ない 感じ 思う 言う 見る くる いく できる 人 今 的 やる www ww さん なん こと れる そう もの heart'.split())
def words(texts):
    c = Counter()
    for mm in texts:
        for tok in t.tokenize(str(mm)):
            pos = tok.part_of_speech.split(',')[0]; b = tok.base_form
            if pos in ('名詞','動詞','形容詞') and len(b) > 1 and b not in STOP: c[b] += 1
    return c

total = len(rows); last = max(r[0] for r in rows)
dur = '%d:%02d:%02d' % (last//3600000, (last//60000)%60, (last//1000)%60)
per_min = Counter(r[0]//60000 for r in rows)
nmin = max(per_min) + 1
series = [per_min.get(i, 0) for i in range(nmin)]
avg_min = round(sum(series)/len(series), 1); peak_min = max(series)

by_min = {}
for off, au, msg in rows: by_min.setdefault(off//60000, []).append(msg)
peaks = []
for mm, c in sorted(per_min.items(), key=lambda x: -x[1])[:8]:
    msgs = by_min[mm]
    w = [x for x, _ in words(msgs).most_common(4)]
    samp = [s.strip() for s in msgs if len(s.strip()) > 2][:3]
    peaks.append({'time': '%d:%02d' % (mm//60, mm%60), 'min': mm, 'count': c, 'words': w, 'samples': samp})

TERMS = ['スコーラー','サバキ','レイド','ドラサイ','バレット','バギン','トラップ','トラガ','天門','ヘブンズ',
         '呪文','マナ','手札','オリカ','ナーフ','VR','SR','デッキ','ビート','耐久']
allmsg = [r[2] for r in rows]
term_counts = sorted(
    [{'term': tm, 'count': sum(tm in x for x in allmsg)} for tm in TERMS if sum(tm in x for x in allmsg) > 0],
    key=lambda x: -x['count'])

POS = '強い つよい いい 良い かっけぇ かっこいい やばい すごい 楽しい 好き 神 うまい うれしい 面白い ナイス 最高'.split()
NEG = '萎え 弱い よわい ナーフ 渋い つまらん きつい 無理 ひどい クソ 残念 がっかり うざい 謎'.split()
pos = sum(any(w in x for w in POS) for x in allmsg)
neg = sum(any(w in x for w in NEG) for x in allmsg)

author_c = Counter(r[1] for r in rows)
uniq = len(author_c)
top10 = [{'author': a, 'count': n} for a, n in author_c.most_common(10)]
top10_share = round(sum(n for _, n in author_c.most_common(10))/total*100, 1)
once = sum(1 for n in author_c.values() if n == 1)

D = {'meta': {'total': total, 'uniq': uniq, 'dur': dur, 'avg_min': avg_min, 'peak_min': peak_min,
              'top10_share': top10_share, 'once': once, 'once_ratio': round(once/uniq*100, 1)},
     'series': series, 'peaks': peaks, 'terms': term_counts,
     'sentiment': {'pos': pos, 'neg': neg}, 'top10': top10}

# ---------- 4. HTML生成 ----------
print("[4/4] レポート生成中…")
def esc(s): return H.escape(str(s))
M, S = D['meta'], D['sentiment']
W, Hh = 1000, 300; PAD_L, PAD_R, PAD_T, PAD_B = 44, 16, 44, 30
pw, ph = W-PAD_L-PAD_R, Hh-PAD_T-PAD_B
n = len(series); mx = max(series) or 1
X = lambda i: PAD_L + (i/(n-1))*pw if n > 1 else PAD_L
Y = lambda v: PAD_T + ph - (v/mx)*ph
pts = [(X(i), Y(v)) for i, v in enumerate(series)]
line_path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
area_path = f"M{pts[0][0]:.1f},{PAD_T+ph:.1f} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{PAD_T+ph:.1f} Z"
ygrid = "".join(
    f'<line x1="{PAD_L}" y1="{PAD_T+ph-fr*ph:.1f}" x2="{W-PAD_R}" y2="{PAD_T+ph-fr*ph:.1f}" class="grid"/>'
    f'<text x="{PAD_L-8}" y="{PAD_T+ph-fr*ph+4:.1f}" class="ytick">{round(mx*fr)}</text>'
    for fr in (0, .25, .5, .75, 1))
xticks = "".join(f'<text x="{X(i):.1f}" y="{Hh-8}" class="xtick">{i//60}h{i%60:02d}m</text>' for i in range(0, n, 30))
dots = "".join(f'<circle cx="{X(p["min"]):.1f}" cy="{Y(series[p["min"]]):.1f}" r="4.5" class="pdot"/>' for p in peaks)
p1 = peaks[0]
dots += f'<text x="{X(p1["min"]):.1f}" y="{Y(series[p1["min"]])-14:.1f}" class="plabel">{p1["time"]} · {p1["count"]}/分</text>'
svg = f'''<svg viewBox="0 0 {W} {Hh}" class="ts" preserveAspectRatio="xMidYMid meet">
<defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#16e0e0" stop-opacity=".34"/><stop offset="1" stop-color="#16e0e0" stop-opacity="0"/></linearGradient></defs>
{ygrid}{xticks}<path d="{area_path}" fill="url(#ar)"/><path d="{line_path}" fill="none" stroke="#16e0e0" stroke-width="2"/>{dots}</svg>'''

_pb = []
for i, p in enumerate(peaks):
    tags = "".join('<span class="tag">' + esc(w) + '</span>' for w in p["words"])
    qs = "".join('<div class="q">' + esc(s) + '</div>' for s in p["samples"])
    _pb.append('<div class="peak"><div class="rank">' + str(i+1) + '</div>'
               '<div class="ptop"><span class="t">⏱ ' + esc(p["time"]) + '</span>'
               '<span class="cnt">' + str(p["count"]) + '<small>/分</small></span></div>'
               '<div class="tags">' + tags + '</div>' + qs + '</div>')
peaks_html = "".join(_pb)
terms = D['terms'][:14]; tmax = max((x['count'] for x in terms), default=1)
_tb = []
for x in terms:
    _tb.append('<div class="bar"><span class="bname">' + esc(x["term"]) + '</span>'
               '<div class="track"><div class="fill" style="width:%.1f%%"></div></div>' % (x["count"]/tmax*100)
               + '<span class="bnum">' + str(x["count"]) + '</span></div>')
terms_html = "".join(_tb)
tot = (S['pos']+S['neg']) or 1; pp = round(S['pos']/tot*100); npn = 100-pp
fans_html = "".join(
    f'<div class="fan"><span class="r">{i+1}</span><span class="a">{esc(f["author"])}</span><span class="c">{f["count"]}</span></div>'
    for i, f in enumerate(D['top10']))
fan_sub = (f"投稿者 {M['uniq']}人中、上位10人が全コメントの {M['top10_share']}% を占める。"
           f"一方で1回だけ投稿した人が {M['once']}人（{M['once_ratio']}%）。")

CSS = """:root{--bg:#07080d;--panel:#0e1018;--panel2:#12141f;--line:#1d2030;--txt:#e8eaf2;--dim:#8389a3;--faint:#565d76;--cyan:#16e0e0;--mag:#ff2d8a;--gold:#ffcf3f;--grn:#39e58c}
*{margin:0;padding:0;box-sizing:border-box}body{background:var(--bg);color:var(--txt);font-family:"Zen Kaku Gothic New","Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;line-height:1.65;background-image:radial-gradient(circle at 15% -10%,rgba(22,224,224,.10),transparent 40%),radial-gradient(circle at 90% 0%,rgba(255,45,138,.10),transparent 42%);background-attachment:fixed}
.wrap{max-width:1080px;margin:0 auto;padding:48px 28px 90px}.mono{font-family:"JetBrains Mono",ui-monospace,monospace}
header{border-bottom:2px solid var(--line);padding-bottom:26px;margin-bottom:40px}
.kicker{font-family:"JetBrains Mono",monospace;font-size:11px;letter-spacing:.32em;color:var(--cyan);text-transform:uppercase;margin-bottom:14px;display:flex;align-items:center;gap:10px}.kicker::before{content:"";width:26px;height:2px;background:var(--cyan)}
h1{font-family:"Bebas Neue","Arial Narrow",sans-serif;font-size:clamp(38px,7vw,76px);line-height:.92;font-weight:400}
h1 .jp{font-family:"Zen Kaku Gothic New";font-weight:900;font-size:.42em;display:block;margin-top:12px;color:var(--txt)}
.src{margin-top:18px;font-size:13px;color:var(--dim);display:flex;flex-wrap:wrap;gap:8px 22px}.src b{color:var(--txt);font-weight:700}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:46px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px 20px;position:relative;overflow:hidden}.kpi::after{content:"";position:absolute;top:0;left:0;width:100%;height:3px;background:var(--accent)}
.kpi .v{font-family:"Bebas Neue","Arial Narrow",sans-serif;font-size:52px;line-height:1;color:var(--accent)}.kpi .l{font-size:12px;color:var(--dim);margin-top:8px}
section{margin-bottom:52px}.h2{display:flex;align-items:baseline;gap:14px;margin-bottom:8px}.h2 .n{font-family:"Bebas Neue",sans-serif;font-size:24px;color:var(--faint)}.h2 h2{font-size:21px;font-weight:900}
.sub{color:var(--dim);font-size:13.5px;margin-bottom:22px;max-width:80ch}.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:24px}
.ts{width:100%;height:auto;display:block}.ts .grid{stroke:rgba(255,255,255,.05)}.ts .ytick{fill:#565d76;font:11px monospace;text-anchor:end}.ts .xtick{fill:#565d76;font:10px monospace;text-anchor:middle}.ts .pdot{fill:#ff2d8a;stroke:#fff;stroke-width:1.4}.ts .plabel{fill:#ffcf3f;font:bold 12px monospace;text-anchor:middle}
.peaks{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.peak{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;position:relative}
.ptop{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}.peak .t{font-family:monospace;font-size:13px;color:var(--cyan);font-weight:700}.peak .cnt{font-family:"Bebas Neue",sans-serif;font-size:30px;color:var(--mag);line-height:.8}.peak .cnt small{font-size:.36em;color:var(--dim);font-family:monospace}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}.tag{font-size:11px;font-family:monospace;background:rgba(22,224,224,.10);color:var(--cyan);border:1px solid rgba(22,224,224,.25);padding:3px 9px;border-radius:20px}
.peak .q{font-size:12.5px;color:var(--dim);border-left:2px solid var(--line);padding-left:10px;margin-top:5px}
.rank{position:absolute;top:-9px;left:-9px;width:26px;height:26px;background:var(--mag);color:#fff;font-family:"Bebas Neue",sans-serif;font-size:17px;display:flex;align-items:center;justify-content:center;border-radius:50%;border:2px solid var(--bg)}.peak:first-child .rank{background:var(--gold);color:#111}
.bars{display:flex;flex-direction:column;gap:9px}.bar{display:grid;grid-template-columns:120px 1fr 48px;align-items:center;gap:14px}.bname{font-size:14px;font-weight:500;text-align:right}.track{height:22px;background:var(--panel2);border-radius:6px;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,var(--cyan),#0fa);border-radius:6px}.bnum{font-family:monospace;font-size:13px;color:var(--dim);text-align:right}
.senti{display:grid;grid-template-columns:1fr auto;gap:24px;align-items:center}.sbar{height:46px;border-radius:10px;display:flex;overflow:hidden;border:1px solid var(--line)}.sbar .p{background:linear-gradient(90deg,var(--grn),#1bd3a0);display:flex;align-items:center;padding-left:16px;font-weight:900;color:#04210f}.sbar .nn{background:linear-gradient(90deg,#ff6a4d,var(--mag));display:flex;align-items:center;justify-content:flex-end;padding-right:16px;font-weight:900;color:#2a0010}
.sleg{font-size:13px;color:var(--dim);white-space:nowrap}.sleg b{font-family:"Bebas Neue",sans-serif;font-size:22px;display:block}.note{font-size:12px;color:var(--faint);margin-top:16px}
.fans{display:grid;grid-template-columns:repeat(2,1fr);gap:8px 26px}.fan{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px dashed var(--line)}.fan .r{font-family:"Bebas Neue",sans-serif;font-size:20px;color:var(--faint);width:26px}.fan .a{flex:1;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fan .c{font-family:monospace;font-size:13px;color:var(--cyan);font-weight:700}
footer{border-top:1px solid var(--line);margin-top:60px;padding-top:24px;font-size:11.5px;color:var(--faint);font-family:monospace;display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px}
.ytbtn{display:inline-flex;align-items:center;gap:9px;margin-top:18px;font-family:"JetBrains Mono",monospace;font-size:13px;font-weight:700;letter-spacing:.03em;color:#04210f;background:linear-gradient(90deg,var(--cyan),#0fa);padding:11px 20px;border-radius:10px;text-decoration:none;transition:.15s;box-shadow:0 0 0 1px rgba(22,224,224,.35)}.ytbtn:hover{transform:translateY(-1px);box-shadow:0 7px 22px rgba(22,224,224,.28)}
@media(max-width:720px){.kpis{grid-template-columns:repeat(2,1fr)}.peaks,.fans{grid-template-columns:1fr}.senti{grid-template-columns:1fr}.bar{grid-template-columns:84px 1fr 38px;gap:10px}}"""

doc = f'''<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ライブチャット分析｜{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=JetBrains+Mono:wght@400;700&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><div class="wrap">
<header><div class="kicker">Live Chat Analytics · DMPS</div>
<h1>FAN PULSE REPORT<span class="jp">ライブチャット盛り上がり分析</span></h1>
<div class="src"><span>対象：<b>{esc(title)}</b></span><span>配信長 <b>{esc(M['dur'])}</b></span><span class="mono">source: youtube live chat replay</span></div><a class="ytbtn" href="https://www.youtube.com/watch?v={esc(VID)}" target="_blank" rel="noopener noreferrer">▶ 元配信をYouTubeで見る</a></header>
<div class="kpis">
<div class="kpi" style="--accent:var(--cyan)"><div class="v">{M['total']:,}</div><div class="l">総コメント数</div></div>
<div class="kpi" style="--accent:var(--mag)"><div class="v">{M['uniq']}</div><div class="l">ユニーク投稿者</div></div>
<div class="kpi" style="--accent:var(--gold)"><div class="v">{M['avg_min']}</div><div class="l">平均コメント / 分</div></div>
<div class="kpi" style="--accent:var(--grn)"><div class="v">{M['peak_min']}</div><div class="l">最大ピーク / 分</div></div></div>
<section><div class="h2"><span class="n">01</span><h2>盛り上がり時系列</h2></div>
<p class="sub">経過時間（分）あたりコメント数。山＝視聴者が反応した瞬間。マゼンタの点がTOPピーク。</p><div class="card">{svg}</div></section>
<section><div class="h2"><span class="n">02</span><h2>ピークの中身：何で沸いたか</h2></div>
<p class="sub">コメントが集中した瞬間に視聴者が話していたワードと生コメント。</p><div class="peaks">{peaks_html}</div></section>
<section><div class="h2"><span class="n">03</span><h2>カード・ギミック言及ランキング</h2></div>
<p class="sub">コメントで言及されたカード／メカニクス名の出現回数。</p><div class="card"><div class="bars">{terms_html}</div></div></section>
<section><div class="h2"><span class="n">04</span><h2>反応の質（簡易センチメント）</h2></div>
<p class="sub">ポジ語とネガ語の出現比。</p><div class="card senti">
<div class="sbar"><div class="p" style="width:{pp}%">{pp}%</div><div class="nn" style="width:{npn}%">{npn}%</div></div>
<div class="sleg"><span style="color:var(--grn)"><b>{S['pos']}</b>ポジ反応</span><br><br><span style="color:var(--mag)"><b>{S['neg']}</b>ネガ反応</span></div></div>
<p class="note">※ 語ベースの簡易判定。傾向把握用。</p></section>
<footer><span>generated by run_report.py · yt-dlp → janome</span><span>{esc(VID)} · {M['total']} msgs</span></footer>
</div></body></html>'''

out = os.path.join(os.getcwd(), f"report_{VID}.html")
open(out, "w", encoding="utf-8").write(doc)

# ギャラリー用メタ(これを build_index.py が集約する)
meta = {"id": VID, "title": title, "category": CATEGORY,
        "total": total, "uniq": uniq, "dur": dur,
        "peak_min": peak_min, "pos": pos, "neg": neg,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "file": os.path.basename(out)}
open(os.path.join(os.getcwd(), f"{VID}.meta.json"), "w", encoding="utf-8").write(
    json.dumps(meta, ensure_ascii=False))

print(f"\n✅ 完成: {out}")
print(f"   {total}コメント / {uniq}人 / 配信長{dur} / 分類:{CATEGORY}")
