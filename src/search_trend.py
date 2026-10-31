"""네이버 데이터랩(검색어 트렌드·쇼핑인사이트)으로 브랜드 검색 추이를 수집하고 시각화합니다.

- 검색어 트렌드: 월별 추이(전체), 연령대·성별·기기별 브랜드 검색 점유율
- 쇼핑인사이트(패션의류 분야 키워드): 브랜드별 연령·성별·기기 클릭 분포
  * 데이터랩 값은 호출마다 최댓값 100 기준의 상대값이라, 서로 다른 호출끼리는 '비율'로만 비교합니다.

사용법 (폴더2 에서 실행):
    python src/search_trend.py              # 수집 + 시각화
    python src/search_trend.py --no-fetch   # 저장된 데이터로 시각화만
출력:
    data/processed/naver_datalab/*.csv
    reports/search_trend_report.html
"""
import argparse
import csv
import html
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from naver_api_hub import ROOT, load_env, request  # noqa: E402

OUT = ROOT / "data" / "processed" / "naver_datalab"
BRANDS = ["유니클로", "스파오", "탑텐"]
COLORS = {"유니클로": "#d6312b", "스파오": "#1f5fa8", "탑텐": "#2e8b57"}
FASHION = "50000000"
START, END = "2024-01-01", "2026-10-30"
RECENT = "2025-11-01"  # 연령·성별·기기 비교 기간(최근 12개월)
# 검색어 트렌드 연령 코드 → 연령대
AGE_GROUPS = {"10대": ["2"], "20대": ["3", "4"], "30대": ["5", "6"], "40대": ["7", "8"], "50대": ["9", "10"], "60대+": ["11"]}
SHOP_AGES = {"10": "10대", "20": "20대", "30": "30대", "40": "40대", "50": "50대", "60": "60대+"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def trend(cid, secret, start, end, **extra):
    body = {"startDate": start, "endDate": end, "timeUnit": "month",
            "keywordGroups": [{"groupName": b, "keywords": [b]} for b in BRANDS], **extra}
    status, data = request("search-trend/v1/search", cid, secret, body)
    if status != 200:
        sys.exit(f"검색어 트렌드 오류 {status}: {data}")
    return [(r["title"], d["period"][:7], d["ratio"]) for r in data["results"] for d in r["data"]]


def shop(cid, secret, path, brand):
    body = {"startDate": RECENT, "endDate": END, "timeUnit": "month", "category": FASHION, "keyword": brand}
    status, data = request(f"shopping/v1/category/keyword/{path}", cid, secret, body)
    if status != 200:
        sys.exit(f"쇼핑인사이트 오류 {status}: {data}")
    return [(brand, d["group"], d["period"][:7], d["ratio"]) for r in data["results"] for d in r["data"]]


def save(name, header, rows):
    with (OUT / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def load(name):
    with (OUT / f"{name}.csv").open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fetch():
    cid, secret = load_env()
    OUT.mkdir(parents=True, exist_ok=True)
    save("monthly", ["brand", "month", "ratio"], trend(cid, secret, START, END))
    rows = []
    for label, codes in AGE_GROUPS.items():
        rows += [(label, *r) for r in trend(cid, secret, START, END, ages=codes)]
    save("monthly_by_age", ["age", "brand", "month", "ratio"], rows)
    rows = []
    for g in ("f", "m"):
        rows += [("여성" if g == "f" else "남성", *r) for r in trend(cid, secret, RECENT, END, gender=g)]
    save("recent_by_gender", ["gender", "brand", "month", "ratio"], rows)
    rows = []
    for dv in ("mo", "pc"):
        rows += [("모바일" if dv == "mo" else "PC", *r) for r in trend(cid, secret, RECENT, END, device=dv)]
    save("recent_by_device", ["device", "brand", "month", "ratio"], rows)
    for path in ("age", "gender", "device"):
        save(f"shop_{path}", ["brand", "group", "month", "ratio"], [r for b in BRANDS for r in shop(cid, secret, path, b)])
    print(f"저장: {OUT}")


# ---------- 집계 ----------
def shares(rows, key, months=None):
    """그룹(key)별로 브랜드 검색량 합을 구해 점유율(%)로."""
    tot = defaultdict(lambda: defaultdict(float))
    for r in rows:
        if months and r["month"] < months:
            continue
        tot[r[key]][r["brand"]] += float(r["ratio"])
    return {k: {b: v[b] / sum(v.values()) * 100 for b in BRANDS} for k, v in tot.items()}


def dist(rows):
    """쇼핑인사이트: 브랜드별 그룹 분포(%)."""
    tot = defaultdict(lambda: defaultdict(float))
    for r in rows:
        tot[r["brand"]][r["group"]] += float(r["ratio"])
    return {b: {g: v / sum(gs.values()) * 100 for g, v in gs.items()} for b, gs in tot.items()}


# ---------- SVG 차트 ----------
W, H, PAD = 760, 300, 48


def line_chart(series, months, title, ymax=None, unit=""):
    ymax = ymax or max(max(v) for v in series.values()) * 1.1
    x = lambda i: PAD + i * (W - PAD * 1.5) / max(1, len(months) - 1)
    y = lambda v: H - PAD + 10 - v / ymax * (H - PAD * 1.6)
    g = [f'<text x="{PAD}" y="18" class="t">{html.escape(title)}</text>']
    for k in range(5):
        v = ymax * k / 4
        g.append(f'<line x1="{PAD}" x2="{W - 10}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>'
                 f'<text x="{PAD - 6}" y="{y(v) + 4:.1f}" class="ax" text-anchor="end">{v:.0f}{unit}</text>')
    step = max(1, len(months) // 12)
    for i, m in enumerate(months):
        if i % step == 0 or i == len(months) - 1:
            g.append(f'<text x="{x(i):.1f}" y="{H - PAD + 28}" class="ax" text-anchor="middle">{m[2:]}</text>')
    # 끝점 라벨이 겹치지 않게 최소 14px 간격으로 밀어냄
    ends = sorted(((y(v[-1]) + 4, n) for n, v in series.items()))
    label_y = {}
    for n_i, (ly, n) in enumerate(ends):
        if n_i and ly - label_y[ends[n_i - 1][1]] < 14:
            ly = label_y[ends[n_i - 1][1]] + 14
        label_y[n] = ly
    for li, (name, vals) in enumerate(series.items()):
        c = COLORS.get(name, ["#666", "#999", "#bbb"][li % 3])
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        g.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2.4"/>')
        g.append(f'<text x="{x(len(vals) - 1) + 4:.1f}" y="{label_y[name]:.1f}" class="lb" fill="{c}">{name}</text>')
    return svg(g, W + 50)


def group_bars(data, groups, title, unit="%"):
    """groups 마다 브랜드 3개 막대."""
    n, bw = len(groups), 16
    gw = (W - PAD * 1.5) / n
    ymax = max(v for d in data.values() for v in d.values()) * 1.15
    y = lambda v: H - PAD + 10 - v / ymax * (H - PAD * 1.6)
    g = [f'<text x="{PAD}" y="18" class="t">{html.escape(title)}</text>',
         f'<line x1="{PAD}" x2="{W - 10}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="grid"/>']
    for gi, grp in enumerate(groups):
        cx = PAD + gi * gw + gw / 2
        g.append(f'<text x="{cx:.1f}" y="{H - PAD + 28}" class="ax" text-anchor="middle">{grp}</text>')
        for bi, b in enumerate(BRANDS):
            v = data[grp][b]
            bx = cx + (bi - 1.5) * (bw + 3)
            g.append(f'<rect x="{bx:.1f}" y="{y(v):.1f}" width="{bw}" height="{y(0) - y(v):.1f}" fill="{COLORS[b]}"/>'
                     f'<text x="{bx + bw / 2:.1f}" y="{y(v) - 3:.1f}" class="vl" text-anchor="middle">{v:.0f}</text>')
    return svg(g + [legend()], W + 50)


def stacked(data, order, title, palette):
    """브랜드별 100% 누적 가로 막대."""
    g = [f'<text x="{PAD}" y="18" class="t">{html.escape(title)}</text>']
    bh, top, left = 34, 40, 80
    span = W - left - 20
    for bi, b in enumerate(BRANDS):
        yy, xx = top + bi * (bh + 14), left
        g.append(f'<text x="{left - 8}" y="{yy + bh / 2 + 5}" class="lb" text-anchor="end">{b}</text>')
        for k, grp in enumerate(order):
            v = data[b].get(grp, 0)
            w = span * v / 100
            g.append(f'<rect x="{xx:.1f}" y="{yy}" width="{w:.1f}" height="{bh}" fill="{palette[k]}"/>')
            if v >= 6:
                g.append(f'<text x="{xx + w / 2:.1f}" y="{yy + bh / 2 + 4}" class="in" text-anchor="middle">{v:.0f}%</text>')
            xx += w
    ly = top + 3 * (bh + 14) + 8
    for k, grp in enumerate(order):
        g.append(f'<rect x="{left + k * 95}" y="{ly}" width="12" height="12" fill="{palette[k]}"/>'
                 f'<text x="{left + k * 95 + 16}" y="{ly + 11}" class="ax">{grp}</text>')
    return svg(g, W + 50, ly + 30)


def legend():
    return "".join(f'<rect x="{W - 230 + i * 75}" y="8" width="12" height="12" fill="{COLORS[b]}"/>'
                   f'<text x="{W - 214 + i * 75}" y="19" class="ax">{b}</text>' for i, b in enumerate(BRANDS))


def svg(parts, w, h=H):
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="Malgun Gothic, sans-serif">'
            + "".join(parts) + "</svg>")


# ---------- 보고서 ----------
def build():
    monthly = load("monthly")
    months = sorted({r["month"] for r in monthly})
    series = {b: [float(r["ratio"]) for r in monthly if r["brand"] == b] for b in BRANDS}
    share_m = {b: [] for b in BRANDS}
    for i, m in enumerate(months):
        s = sum(series[b][i] for b in BRANDS)
        for b in BRANDS:
            share_m[b].append(series[b][i] / s * 100)

    by_age = load("monthly_by_age")
    ages = list(AGE_GROUPS)
    age_share = shares(by_age, "age", RECENT)
    gender_share = shares(load("recent_by_gender"), "gender")
    device_share = shares(load("recent_by_device"), "device")
    shop_age = dist(load("shop_age"))
    shop_age = {b: {SHOP_AGES[k]: v for k, v in d.items()} for b, d in shop_age.items()}
    shop_gender = {b: {("여성" if k == "f" else "남성"): v for k, v in d.items()} for b, d in dist(load("shop_gender")).items()}
    shop_device = {b: {("모바일" if k == "mo" else "PC"): v for k, v in d.items()} for b, d in dist(load("shop_device")).items()}

    # 연령대별 월간 점유율 추이(스파오·탑텐 점유율이 가장 큰 연령대 확인용)
    age_month_share = {}
    for a in ages:
        rs = [r for r in by_age if r["age"] == a]
        ms = sorted({r["month"] for r in rs})
        val = {(r["brand"], r["month"]): float(r["ratio"]) for r in rs}
        age_month_share[a] = {b: [val[(b, m)] / max(1e-9, sum(val[(x, m)] for x in BRANDS)) * 100 for m in ms]
                              for b in BRANDS}

    # 요약 지표
    yoy = {}
    for b in BRANDS:
        cur = sum(series[b][-12:])
        prev = sum(series[b][-24:-12])
        yoy[b] = (cur / prev - 1) * 100
    peak = {b: months[max(range(len(months)), key=lambda i: series[b][i])] for b in BRANDS}
    last12 = {b: sum(series[b][-12:]) for b in BRANDS}
    tot12 = sum(last12.values())

    charts = [
        ("월별 검색 추이", line_chart(series, months, "월별 검색량 지수 (전체 최댓값=100)"),
         "세 브랜드를 한 번에 조회해 같은 기준(최댓값 100)으로 비교한 값입니다."),
        ("월별 검색 점유율", line_chart(share_m, months, "3사 합계 대비 검색 점유율 (%)", 100, "%"),
         "월마다 세 브랜드 검색량 합을 100%로 놓은 점유율입니다."),
        ("연령대별 검색 점유율", group_bars(age_share, ages, f"연령대별 3사 검색 점유율 (%, {RECENT[:7]} ~ 최근)"),
         "연령대별로 따로 조회한 뒤 그 연령대 안에서 3사 점유율을 구했습니다."),
    ]
    small = "".join(f'<div class="sm">{line_chart(age_month_share[a], sorted({r["month"] for r in by_age if r["age"] == a}), f"{a} 검색 점유율 추이 (%)", 100, "%")}</div>' for a in ages)
    charts.append(("연령대별 월별 점유율 추이", f'<div class="grid2">{small}</div>',
                   "연령대마다 3사 점유율이 2024년 이후 어떻게 움직였는지 보여줍니다."))
    charts.append(("성별·기기별 검색 점유율",
                   group_bars({**gender_share, **device_share}, ["여성", "남성", "모바일", "PC"],
                              "성별·기기별 3사 검색 점유율 (%, 최근 12개월)"), ""))
    age_pal = ["#f2c14e", "#f78154", "#d6312b", "#8c2f39", "#4d5382", "#2e4057"]
    charts.append(("브랜드별 쇼핑 클릭 연령 분포",
                   stacked(shop_age, ages, "패션의류 분야 브랜드 키워드 클릭의 연령 분포 (최근 12개월)", age_pal),
                   "쇼핑인사이트 값으로, 각 브랜드를 클릭한 사용자의 연령 구성입니다."))
    charts.append(("브랜드별 쇼핑 클릭 성별·기기 분포",
                   stacked(shop_gender, ["여성", "남성"], "성별 분포", ["#c0392b", "#2c3e50"])
                   + stacked(shop_device, ["모바일", "PC"], "기기 분포", ["#16a085", "#7f8c8d"]), ""))

    kpi = "".join(
        f'<div class="kpi" style="border-color:{COLORS[b]}"><b style="color:{COLORS[b]}">{b}</b>'
        f'<span>최근 12개월 점유율 <strong>{last12[b] / tot12 * 100:.0f}%</strong></span>'
        f'<span>전년 대비 검색량 <strong>{yoy[b]:+.0f}%</strong></span><span>최고 월 {peak[b]}</span></div>'
        for b in BRANDS)
    body = "".join(f'<section><h2>{t}</h2>{c}<p class="note">{n}</p></section>' for t, c, n in charts)
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SPA 3사 검색 추이</title><style>
body{{font-family:"Malgun Gothic",sans-serif;max-width:1100px;margin:0 auto;padding:16px;background:#f6f7f9;color:#222}}
section{{background:#fff;border-radius:8px;padding:12px 16px;margin:14px 0}} h2{{font-size:18px;margin:4px 0 8px}}
svg{{width:100%;height:auto}} .t{{font-size:14px;font-weight:700}} .ax{{font-size:11px;fill:#555}} .lb{{font-size:12px;font-weight:700}}
.vl{{font-size:10px;fill:#333}} .in{{font-size:11px;fill:#fff;font-weight:700}} .grid line,.grid{{stroke:#e6e8eb}}
line.grid{{stroke:#e6e8eb}} .note{{font-size:12px;color:#666;margin:4px 0 0}} .kpis{{display:flex;gap:12px;flex-wrap:wrap}}
.kpi{{flex:1;min-width:200px;background:#fff;border-left:5px solid;border-radius:6px;padding:10px 12px;display:flex;flex-direction:column;gap:3px;font-size:13px}}
.kpi b{{font-size:16px}} div.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:8px}}
</style></head><body><h1>SPA 3사 검색 추이: 유니클로 · 스파오 · 탑텐</h1>
<p class="note">출처: 네이버 데이터랩 검색어 트렌드·쇼핑인사이트(패션의류 분야), {START} ~ {END}. 수치는 상대 지수와 그로부터 계산한 점유율입니다.</p>
<div class="kpis">{kpi}</div>{body}</body></html>"""
    (ROOT / "reports" / "search_trend_report.html").write_text(page, encoding="utf-8")

    # 해석용 숫자 출력
    print("최근12개월 점유율:", {b: round(last12[b] / tot12 * 100, 1) for b in BRANDS})
    print("전년대비:", {b: round(v, 1) for b, v in yoy.items()}, "최고월:", peak)
    print("연령대별 점유율:", {a: {b: round(v, 1) for b, v in d.items()} for a, d in age_share.items()})
    print("성별:", {k: {b: round(v, 1) for b, v in d.items()} for k, d in gender_share.items()})
    print("기기:", {k: {b: round(v, 1) for b, v in d.items()} for k, d in device_share.items()})
    print("쇼핑 연령분포:", {b: {k: round(v, 1) for k, v in d.items()} for b, d in shop_age.items()})
    print("쇼핑 성별:", {b: {k: round(v, 1) for k, v in d.items()} for b, d in shop_gender.items()})
    print("쇼핑 기기:", {b: {k: round(v, 1) for k, v in d.items()} for b, d in shop_device.items()})
    print("월별 점유율(분기 샘플):", {b: [f"{months[i]}:{share_m[b][i]:.0f}" for i in range(0, len(months), 3)] for b in BRANDS})
    for a in ages:
        d = age_month_share[a]
        print(f"{a} 점유율 처음→최근:", {b: f"{d[b][0]:.0f}→{sum(d[b][-3:]) / 3:.0f}" for b in BRANDS})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-fetch", action="store_true")
    if not p.parse_args().no_fetch:
        fetch()
    build()
