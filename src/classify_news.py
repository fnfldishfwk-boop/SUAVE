"""정제 뉴스(_clean.csv)를 기사당 하나의 주제로 분류합니다.

주제: 제품 출시 / 협업 / 할인·행사 / 실적·사업 / 기타
제목을 먼저 보고, 제목에서 정해지지 않으면 요약문을 봅니다. CATEGORIES 에서 위에 있는 주제가 우선하며,
사회공헌·수상·인물·회고 기사(PRE_OTHER)는 제목 기준으로 먼저 기타로 보냅니다.

사용법 (폴더2 에서 실행):
    python src/classify_news.py naver_news_20261031_1034
출력:
    data/processed/naver_news/<stem>_category.csv
    reports/brand_news_categories.md
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "naver_news"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OTHER = "기타"
# 사회공헌·수상·인물·회고 기사는 다른 키워드가 있어도 기타로 먼저 분류
PRE_OTHER = r"PR대상|PR프랙티스|수상|사회공헌|후원금|기부(?!터)|재해보험|느린학습자|천천히 함께|대학생|Who Is|아카이브|10년 전 오늘"
CATEGORIES = [
    ("협업", r"협업|컬래버|콜라보|K/DA|라이엇|교보|캐릭터|IP |먼작귀|치이카와|F\.?RISSO|앤더슨|이토 ?준지|와 손잡"),
    ("할인·행사", r"할인|세일|텐텐데이|반값|팝업|워크숍|캠페인|행사|디즈니|프로모션|이벤트|기획전|페스타|응원"),
    ("실적·사업", r"매출|영업이익|영업익|실적|시장|점유|매장|출점|오픈|리뉴얼|새단장|점포|플래그십|호점|입점|인사|배당|"
                 r"상장|성장|가격|인상|앱|사용자|순위|전략|경쟁|직영|상권|관광|사업|캐시카우|성공방정식|넥스트|재무|"
                 r"명동|격돌|대전|지각변동|추월|질주|생산|승부수|디지털"),
    ("제품 출시", r"출시|선봬|선보|신제품|신상|컬렉션|라인업|론칭|에어테크|웜테크|플리스|패딩|니트|재킷|내의|스웨터|"
                 r"쿨에어|냉감|쿨링|기능성|언더웨어|속옷|바지|아우터|키즈웨어"),
]


def classify(r):
    if re.search(PRE_OTHER, r["title"]):
        return OTHER, "title"
    for field in ("title", "description"):
        for name, pat in CATEGORIES:
            if re.search(pat, r[field]):
                return name, field
    return OTHER, ""


def main():
    stem = sys.argv[1]
    rows = list(csv.DictReader((DATA / f"{stem}_clean.csv").open(encoding="utf-8-sig")))
    for r in rows:
        r["category"], r["category_by"] = classify(r)

    fields = ["brand", "category", "category_by", "pubDate", "title", "description",
              "originallink", "link", "verdict", "dup_count", "dup_group"]
    with (DATA / f"{stem}_category.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    brands = list(dict.fromkeys(r["brand"] for r in rows))
    names = ["제품 출시", "협업", "할인·행사", "실적·사업", OTHER]  # 표시 순서
    esc = lambda s: s.replace("|", "\\|")
    md = [f"# 브랜드별 뉴스 주제 분류 (출처: {stem}_clean.csv)", "",
          "기사당 하나의 주제. 우선순위: (사회공헌·수상·인물 → 기타) > 협업 > 할인·행사 > 실적·사업 > 제품 출시 > 기타 "
          "(제목 우선, 없으면 요약). 매장 출점·가격 정책은 실적·사업에 포함.", "",
          "## 주제별 건수", "", "| 주제 | " + " | ".join(brands) + " |", "|---|" + "---:|" * len(brands)]
    counts = {b: Counter(r["category"] for r in rows if r["brand"] == b) for b in brands}
    for n in names:
        md.append(f"| {n} | " + " | ".join(f"{counts[b][n]} ({counts[b][n] / sum(counts[b].values()):.0%})"
                                             for b in brands) + " |")
    md.append("")
    for b in brands:
        md += [f"## {b}", ""]
        for n in names:
            sub = [r for r in rows if r["brand"] == b and r["category"] == n]
            if not sub:
                continue
            md += [f"### {n} ({len(sub)}건)", "", "| 날짜 | 제목 | 동일 보도 | 원문 |", "|---|---|---:|---|"]
            for r in sub:
                md.append(f"| {r['pubDate'][:10]} | {esc(r['title'])} | {r['dup_count']} | "
                          f"[원문]({r['originallink'] or r['link']}) |")
            md.append("")
    (ROOT / "reports" / "brand_news_categories.md").write_text("\n".join(md), encoding="utf-8")

    for b in brands:
        print(f"\n== {b}: " + ", ".join(f"{n} {counts[b][n]}" for n in names))
        for r in (r for r in rows if r["brand"] == b):
            print(f"  {r['category']:<5} {r['pubDate'][5:10]} {r['title'][:48]}")


if __name__ == "__main__":
    main()
