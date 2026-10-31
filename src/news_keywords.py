"""브랜드×주제별 주요 키워드를 BoW(빈도)와 TF-IDF로 추출하고 워드 클라우드(SVG)를 만듭니다.

- 문서: 기사 1건 = 제목 + 요약
- BoW: 그룹(브랜드×주제) 안에서 단어 등장 횟수 합
- TF-IDF: 그룹 하나를 문서 하나로 보고(15개 문서) 계산 → 다른 브랜드·주제에 비해 그 그룹에서 두드러지는 단어
- 토큰화: 형태소 분석기 없이 정규식 + 조사·어미 제거 (외부 라이브러리 없음)
- 브랜드명·운영사명은 모든 그룹에 깔리므로 불용어로 제외

사용법 (폴더2 에서 실행):
    python src/news_keywords.py naver_news_20261031_1034
출력:
    reports/tables/news/<stem>_keywords.csv
    reports/figures/news_wordcloud/<브랜드>_<주제>_<bow|tfidf>.svg, index.html
    reports/news_keywords_tables.md
"""
import csv
import html
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "naver_news"
FIG = ROOT / "reports" / "figures" / "news_wordcloud"
TABLES = ROOT / "reports" / "tables" / "news"
TOP_N = 15
CLOUD_N = 40
CATEGORIES = ["제품 출시", "협업", "할인·행사", "실적·사업", "기타"]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 길이가 긴 것부터 떼어냄. '이·가·로'처럼 명사 끝 글자와 겹치기 쉬운 한 글자 조사는 넣지 않음(유니클로, 텐텐데이)
SUFFIXES = sorted("""은 는 을 를 의 에 에서 에게 으로 와 과 도 만 까지 부터 보다 처럼 이나 이며 이고
    으로는 에서는 에는 과의 와의 에서도 에도 으로도 하는 했다 한다 하고 하며 했고
    된 되는 됐다 된다 하기 하면 적인 들이 들의 들은 들을""".split(),
                  key=len, reverse=True)
PROTECT = {"발열내의", "내의", "흥행몰이", "가을", "겨울", "하늘", "마을", "기능성", "다이소", "도쿄"}
STOP = set("""유니클로 스파오 탑텐 탑텐키즈 스파오키즈 신성통상 이랜드월드 이랜드 UNIQLO SPAO TOPTEN TOPTEN10 TOPTEN KIDS
    브랜드 SPA 패션 제조 유통 일괄 일괄형 운영 운영하는 전개 전개하는 대표 기자 뉴스 사진 제공 업계 업계에
    따르면 밝혔다 지난 올해 이번 이날 통해 위해 함께 다양한 있다 있는 없다 것으로 것이 것을 등을 등이 등의 등
    대한 관련 가운데 이후 최근 오는 현재 가장 더욱 특히 또한 한편 이어 다음 각각 모두 이상 이하 기준 대비 정도
    하나 경우 때문 만에 만원 억원 원대 지난해 전년 동기 올해는 다는 라고 이라고 했다고 그러나 하지만 그는 이를
    공개 선보인다 선보였다 이유 옛말 현장 기사 보는 오늘 해당 사용 안내 왼쪽 시작했 비슷 정리 제안 대신 회사 자사
    조동주 염태순 래퍼이자 더트래커 중심 강화 확대 공략 진행 마련 계획 예정 설명 관계자 고객 상품 제품 시즌 FW
    다시 역시 동안 어디로 가볼까 비슷한 빠진 공식 함께한 스파오라 이유민 모으 입기 시작했나 맞추고 제대로 기존
    못한 확립하지 역대 주도 향후 과제 관건 차별화가 아이템화 줄어들까 뛰어들었다 협업한 개발한 소재가""".split())
DATE_LIKE = re.compile(r"\d+(년|월|일|년간|일부터|일까지|월호|살|시|분)?")


def tokenize(text):
    out = []
    for w in re.findall(r"[가-힣]+|[A-Za-z][A-Za-z0-9.&]*|\d+[가-힣%]*", html.unescape(text)):
        if re.fullmatch(r"[가-힣]+", w) and w not in STOP and w not in PROTECT:
            for s in SUFFIXES:
                if w.endswith(s):
                    w = w[: -len(s)]
                    break
            # 브랜드명 + 한 글자 조사(탑텐이, 유니클로가, 스파오로)
            if w[:-1] in STOP and w[-1] in "이가로":
                continue
        if len(w) < 2 or w in STOP or w.upper() in STOP or DATE_LIKE.fullmatch(w):
            continue
        out.append(w)
    return out


def main():
    stem = sys.argv[1]
    rows = list(csv.DictReader((DATA / f"{stem}_category.csv").open(encoding="utf-8-sig")))
    brands = list(dict.fromkeys(r["brand"] for r in rows))
    groups = {(b, c): [r for r in rows if r["brand"] == b and r["category"] == c] for b in brands for c in CATEGORIES}
    groups = {k: v for k, v in groups.items() if v}

    bow = {k: Counter(t for r in v for t in tokenize(r["title"] + " " + r["description"])) for k, v in groups.items()}
    df = Counter(t for c in bow.values() for t in c)
    n_docs = len(bow)
    tfidf = {}
    for k, c in bow.items():
        total = sum(c.values())
        # 스무딩한 IDF: 모든 그룹에 나오는 단어도 0이 되지 않도록 +1
        tfidf[k] = {t: (n / total) * (math.log((1 + n_docs) / (1 + df[t])) + 1) for t, n in c.items()}

    FIG.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    out_rows, md, cards = [], [], []
    md += ["# 브랜드×주제별 주요 키워드: BoW vs TF-IDF", "",
           f"출처: `{stem}_category.csv` (브랜드별 정제 50건). 그룹별 상위 {TOP_N}개. "
           "TF-IDF는 15개 브랜드×주제 그룹을 문서로 보고 계산했습니다.", ""]
    for b in brands:
        md += [f"## {b}", ""]
        for c in CATEGORIES:
            if (b, c) not in groups:
                continue
            k = (b, c)
            top_b = bow[k].most_common(TOP_N)
            top_t = sorted(tfidf[k].items(), key=lambda kv: -kv[1])[:TOP_N]
            sb, st = {t for t, _ in top_b}, {t for t, _ in top_t}
            for rank, ((tb, nb), (tt, vt)) in enumerate(zip(top_b, top_t), 1):
                out_rows.append({"brand": b, "category": c, "articles": len(groups[k]), "rank": rank,
                                 "bow_term": tb, "bow_count": nb, "tfidf_term": tt, "tfidf_score": round(vt, 4)})
            md += [f"### {c} ({len(groups[k])}건)", "",
                   f"- 공통: {', '.join(t for t, _ in top_b if t in st) or '없음'}",
                   f"- BoW에만: {', '.join(t for t, _ in top_b if t not in st) or '없음'}",
                   f"- TF-IDF에만: {', '.join(t for t, _ in top_t if t not in sb) or '없음'}", "",
                   "| 순위 | BoW | 빈도 | TF-IDF | 점수 |", "|---:|---|---:|---|---:|"]
            for i, ((tb, nb), (tt, vt)) in enumerate(zip(top_b, top_t), 1):
                md.append(f"| {i} | {tb} | {nb} | {tt} | {vt:.3f} |")
            md.append("")
            for method, weights in (("bow", dict(bow[k].most_common(CLOUD_N))),
                                    ("tfidf", dict(sorted(tfidf[k].items(), key=lambda kv: -kv[1])[:CLOUD_N]))):
                name = f"{b}_{c.replace('·', '-')}_{method}.svg"
                (FIG / name).write_text(cloud_svg(weights, seed=sum(map(ord, name))), encoding="utf-8")
                cards.append((b, c, method, name, len(groups[k])))

    with (TABLES / f"{stem}_keywords.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    (ROOT / "reports" / "news_keywords_tables.md").write_text("\n".join(md), encoding="utf-8")
    (FIG / "index.html").write_text(gallery(cards, brands), encoding="utf-8")
    print("\n".join(md))


PALETTE = ["#1f4e79", "#2e75b6", "#c55a11", "#548235", "#7030a0", "#bf9000", "#2f5597", "#a5243d"]


def text_width(word, size):
    return sum(size * (1.0 if "가" <= ch <= "힣" else 0.62) for ch in word)


def cloud_svg(weights, width=520, height=320, seed=0):
    """나선형 배치로 겹치지 않게 단어를 놓는 간단한 워드 클라우드."""
    rnd = random.Random(seed)
    items = sorted(weights.items(), key=lambda kv: -kv[1])
    if not items:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'
    hi, lo = items[0][1], items[-1][1]
    placed, parts = [], []
    for i, (word, wgt) in enumerate(items):
        ratio = (wgt - lo) / (hi - lo) if hi > lo else 1
        size = 13 + ratio ** 0.8 * 43
        w, h = text_width(word, size), size * 1.1
        t, step = rnd.random() * 6.28, 0
        while step < 2500:
            r = 2.2 * t
            x, y = width / 2 + r * math.cos(t) * 1.5 - w / 2, height / 2 + r * math.sin(t) - h / 2
            box = (x, y, x + w, y + h)
            inside = box[0] >= 4 and box[1] >= 4 and box[2] <= width - 4 and box[3] <= height - 4
            if inside and all(box[2] < p[0] or box[0] > p[2] or box[3] < p[1] or box[1] > p[3] for p in placed):
                placed.append(box)
                parts.append(f'<text x="{x:.1f}" y="{y + size * 0.88:.1f}" font-size="{size:.1f}" '
                             f'fill="{PALETTE[i % len(PALETTE)]}" font-weight="{700 if ratio > 0.4 else 500}">'
                             f'{html.escape(word)}</text>')
                break
            t += 0.12
            step += 1
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'font-family="Malgun Gothic, Apple SD Gothic Neo, sans-serif">'
            f'<rect width="100%" height="100%" fill="#ffffff"/>{"".join(parts)}</svg>')


def gallery(cards, brands):
    sec = []
    for b in brands:
        cells = []
        for c in CATEGORIES:
            pair = [x for x in cards if x[0] == b and x[1] == c]
            if not pair:
                continue
            n = pair[0][4]
            # SVG를 페이지에 직접 넣어 파일 하나로 열리게 함
            imgs = "".join(f'<figure><figcaption>{"BoW (빈도)" if m == "bow" else "TF-IDF"}</figcaption>'
                           f'{(FIG / name).read_text(encoding="utf-8")}</figure>' for _, _, m, name, _ in pair)
            note = ' <span class="warn">기사 수가 적어 참고용</span>' if n < 5 else ""
            cells.append(f'<div class="row"><h3>{c} <small>({n}건)</small>{note}</h3><div class="pair">{imgs}</div></div>')
        sec.append(f"<section><h2>{b}</h2>{''.join(cells)}</section>")
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>브랜드×주제 워드 클라우드</title><style>
body{{font-family:"Malgun Gothic",sans-serif;margin:0 auto;max-width:1120px;padding:16px;background:#f6f7f9;color:#222}}
h2{{border-bottom:2px solid #2e75b6;padding-bottom:4px}} .row{{background:#fff;border-radius:8px;padding:8px 12px;margin:12px 0}}
.pair{{display:flex;gap:12px;flex-wrap:wrap}} figure{{margin:0;flex:1;min-width:280px}} figure svg{{width:100%;height:auto;border:1px solid #e3e6ea;border-radius:6px}}
figcaption{{font-size:13px;color:#555;margin-bottom:4px}} .warn{{font-size:12px;color:#c55a11;font-weight:normal}}
</style></head><body><h1>브랜드×주제별 워드 클라우드 (BoW vs TF-IDF)</h1>
<p>BoW는 그룹 안 단어 빈도, TF-IDF는 15개 브랜드×주제 그룹 중 그 그룹에서 두드러지는 단어입니다. 브랜드명·운영사명은 제외했습니다.</p>
{''.join(sec)}</body></html>"""


if __name__ == "__main__":
    main()
