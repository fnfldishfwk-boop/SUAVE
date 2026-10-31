"""브랜드별 뉴스 정제본(_clean.csv)을 집계해 분석 표를 만듭니다.

사용법 (폴더2 에서 실행):
    python src/analyze_news.py naver_news_20261031_1034
출력:
    reports/tables/news/<stem>_*.csv   집계표
    reports/news_analysis_tables.md    보고서에 붙일 표
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "naver_news"
TABLES = ROOT / "reports" / "tables" / "news"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 제목+요약 키워드로 붙이는 주제 태그 (한 기사에 여러 개 가능)
TOPICS = {
    "가격·할인": r"가격|할인|인상|세일|텐텐데이|반값|\d+만\s?원|원대",
    "매장·출점": r"매장|점포|출점|오픈|리뉴얼|새단장|플래그십|\d+호점",
    "협업·IP": r"협업|컬래버|콜라보|캐릭터|K/DA|교보|먼작귀|치이카와|디즈니",
    "상품·소재": r"패딩|플리스|니트|발열|내의|소재|컬렉션|신제품|에어테크|웜테크|히트텍|팬츠|재킷",
    "실적·시장": r"매출|영업이익|실적|성장률|시장 규모|순위|사용자|증가율|판매량",
    "마케팅·모델": r"캠페인|모델|앰버서더|화보|팝업|행사",
    "ESG·사회공헌": r"사회공헌|기부|수선|순환|ESG|재해|후원|공익",
    "경영·기업": r"대표이사|인사|배당|상장|지분|경영|오너",
}


def main():
    stem = sys.argv[1]
    rows = list(csv.DictReader((DATA / f"{stem}_clean.csv").open(encoding="utf-8-sig")))
    review = list(csv.DictReader((DATA / f"{stem}_review.csv").open(encoding="utf-8-sig")))
    TABLES.mkdir(parents=True, exist_ok=True)
    brands = list(dict.fromkeys(r["brand"] for r in rows))
    by_brand = {b: [r for r in rows if r["brand"] == b] for b in brands}
    for r in rows:
        text = r["title"] + " " + r["description"]
        r["topics"] = [t for t, p in TOPICS.items() if re.search(p, text)]
        r["week"] = datetime.strptime(r["pubDate"][:10], "%Y-%m-%d").strftime("%G-W%V")

    # 1. 개요
    overview = []
    for b in brands:
        sub = by_brand[b]
        start = sub[-1]["pubDate"][:10]
        window = [r for r in review if r["brand"] == b and r["pubDate"][:10] >= start]
        overview.append({
            "브랜드": b, "기간": f"{start} ~ {sub[0]['pubDate'][:10]}",
            "기간 내 수집": len(window), "정제": len(sub),
            "관련": sum(r["verdict"] == "관련" for r in sub),
            "애매-유지": sum(r["verdict"] == "애매-유지" for r in sub),
            "보도량(동일 보도 포함)": sum(int(r["dup_count"]) for r in sub),
            "정제 비율": f"{len(sub) / len(window):.0%}",
        })

    # 2. 주제 분포
    topics = []
    for t in TOPICS:
        row = {"주제": t}
        for b in brands:
            n = sum(t in r["topics"] for r in by_brand[b])
            row[b] = f"{n} ({n / len(by_brand[b]):.0%})"
        topics.append(row)

    # 3. 주요 이슈 (동일 보도 수 기준)
    issues = []
    for b in brands:
        for r in sorted(by_brand[b], key=lambda r: -int(r["dup_count"]))[:6]:
            issues.append({"브랜드": b, "날짜": r["pubDate"][:10], "이슈(대표 기사)": r["title"],
                           "동일 보도": int(r["dup_count"]), "원문": r["originallink"] or r["link"]})

    # 4. 주별 기사 수
    weeks = sorted({r["week"] for r in rows})
    weekly = []
    for w in weeks:
        row = {"주차": w}
        for b in brands:
            sub = [r for r in by_brand[b] if r["week"] == w]
            row[f"{b} 기사"] = len(sub)
            row[f"{b} 보도량"] = sum(int(r["dup_count"]) for r in sub)
        weekly.append(row)

    # 5. 판정 사유 (제외 기사)
    reasons = []
    for b in brands:
        start = by_brand[b][-1]["pubDate"][:10]
        c = Counter((r["verdict"], r["reason"]) for r in review
                    if r["brand"] == b and r["pubDate"][:10] >= start and r["verdict"] in ("무관", "애매-제외"))
        for (v, reason), n in c.most_common(5):
            reasons.append({"브랜드": b, "판정": v, "사유": reason, "건수": n})

    tables = {"overview": overview, "topics": topics, "issues": issues, "weekly": weekly, "excluded": reasons}
    for name, data in tables.items():
        with (TABLES / f"{stem}_{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)

    md = []
    titles = {"overview": "수집·정제 개요", "topics": "주제 분포 (정제 기사 기준, 중복 태그 허용)",
              "issues": "주요 이슈 (동일 보도 수 상위)", "weekly": "주별 기사 수 (기사 = 정제 건수, 보도량 = 동일 보도 포함)",
              "excluded": "제외 사유 상위 (정제 기간 내)"}
    for name, data in tables.items():
        md += [f"### {titles[name]}", "", md_table(data), ""]
    (ROOT / "reports" / "news_analysis_tables.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


def md_table(data):
    keys = list(data[0].keys())
    cell = lambda v: str(v).replace("|", "\\|")
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    for d in data:
        vals = [f"[원문]({d[k]})" if k == "원문" else cell(d[k]) for k in keys]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
