"""수집한 브랜드 뉴스에 관련성·중복 판정을 붙이고, 브랜드별 최신 50건 정제본을 만듭니다.

판정 기준은 CLAUDE.md 의 '뉴스 정제 규칙'을 따릅니다. 순위가 아닌 키워드 규칙으로 판정하므로
새로 수집한 파일에도 그대로 적용됩니다. 새 이슈가 생기면 RULES/EVENTS 를 보강합니다.

사용법 (폴더2 에서 실행):
    python src/review_news.py                         # 가장 최근 수집 파일
    python src/review_news.py naver_news_20261031_1034.csv
"""
import csv
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "processed" / "naver_news"
TARGET = 50
KEEP = {"관련", "애매-유지"}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 브랜드명과 같은 글자가 들어간 다른 고유명사. 이 표현을 지우고도 브랜드명이 남지 않으면 무관
HOMONYMS = {
    "유니클로": r"유니클로 ?(필드|앳)",
    "탑텐": r"텐아시아|탑텐 ?가요쇼|뉴스 ?탑텐|탑텐 ?어워즈|아티스트 ?탑텐|TOP TEN|베스트송 탑텐|탑텐 안에|Top ?10|엔터테인먼트 브랜드 '탑텐'|재팬 ?탑텐|탑텐 ?TV|가요 ?탑텐",
    "스파오": r"$^",
}

# (판정, 정규식, 사유, 제목에 브랜드가 있어도 적용 여부). 위에서부터 먼저 맞는 규칙 적용
RULES = [
    ("무관", r"기프티엘|런드리고|모두싸인|오타니|다저스", "다른 주제 기사(쿠폰 해킹·세탁 데이터·계약 솔루션·야구 등)", True),
    ("무관", r"평균 연봉|1000만엔|최고 부자|야나이 다다시", "기업 연봉·부호 순위 기사", True),
    ("무관", r"가요톱|넷플릭스 코리아", "동음이의어: 방송·OTT 순위의 '탑텐(TOP10)'", False),
    ("애매-제외", r"정현석|에프알엘코리아 대표|FRL코리아 대표", "전 운영사 대표의 롯데 인사 기사", False),
    ("애매-제외", r"청량리|벨리타운", "쇼핑몰 방문기, 입점 매장 나열", False),
    ("애매-제외", r"이랜드재단|메이크오버", "이랜드재단 사회공헌, 매장 나열", False),
    ("애매-제외", r"최종양|박성수 회장의|전문경영인|신용등급|지분도 경영도", "이랜드 그룹 경영·재무 기사, 계열 브랜드 나열", False),
    ("애매-제외", r"^\[?MD포토|포토엔|\[포토\]|하트|미소|미모|손인사|여신", "행사 참석 연예인 사진 기사", False),
    ("애매-제외", r"멤버십 혜택|면세점|촬영로봇|롯데몰|갤러리아|J패션|자매 브랜드 GU|치이카와 붐|팝콘통|다이소|돈키호테",
     "다른 업체·IP 기사, 입점·제휴처로 언급", False),
    ("애매-유지", r"Weekly New키즈|야구 직관", "주제는 다르지만 브랜드 협업·팝업 상세 내용", False),
]
# 제목 기준 제외 (제목에 자기 브랜드가 없을 때만). (정규식, 사유)
TITLE_EXCLUDES = [
    (r"무신사|신발 사진", "무신사 기사, 경쟁사·과거 일화로 언급"),
    (r"^\[[^\]]*(브리핑|유통|오늘|소식|Pick|단신|레이더|똑똑한|잘먹잘살|포인트|Weekly|돋보기|이모저모|패션뷰티)[^\]]*\]|外",
     "여러 업체 소식을 묶은 브리핑 기사"),
]
OTHER_BRANDS = {"유니클로": r"탑텐|스파오", "스파오": r"탑텐|유니클로", "탑텐": r"스파오|유니클로"}

# 같은 사건의 다매체 보도 그룹. (그룹명, 제목+요약 정규식). 위에서부터 먼저 맞는 그룹에 배정
EVENTS = {
    "유니클로": [
        ("일본 양말 가격 인상 철회", r"철회"),
        ("일본 가격 인상 발표", r"평균 4%|감동팬츠|감탄팬츠|묶음 할인|가격 인상|가격 오른|가격을 인상"),
        ("F.RISSO 니트 컬렉션", r"F\.?RISSO|프란체스코 리소"),
        ("JW 앤더슨 협업 컬렉션", r"JW ?앤더슨|and JW"),
        ("패스트리테일링 연간 실적·세계 2위 전망", r"H&M|H＆M|세계 2위|역대 최대|사상 최대|영업익 32%"),
        ("제주SK UTme 협업", r"제주SK|제주, 유니클로|프로축구단 최초"),
        ("목동점 확장·의왕점 개점", r"목동점|의왕|셀프계산대"),
        ("희망브리지 재해보험 지원", r"희망브리지"),
        ("라이엇 K/DA UTme 협업", r"K/DA|라이엇"),
        ("국제 수선의 날 워크숍", r"수선"),
        ("디즈니런 공식 협찬", r"디즈니 ?런|디즈니 세상|디즈니 덕후"),
        ("뷰티·패션 앱 사용자 증가율 1위", r"앱 사용자|사용자 증가율|이용자 증가율|모바일 3강"),
        ("한국PR대상 사회공헌 캠페인", r"PR대상"),
        ("아시아 브랜드 평가 순위", r"29위에서 34위|29위→34위"),
        ("헤럴드경제 SPA 키즈 패딩 기사", r"등골브레이커는 옛말|9만원대 SPA 패딩"),
    ],
    "스파오": [
        ("이랜드 30년 소장품·기네스 공개", r"소장품|기네스|아카이브|의류 도서관|수장고"),
        ("스파오 프렌즈 캐릭터 팝업", r"스파오 ?프렌즈'? ?팝업"),
        ("스윙스 성수점 방문", r"스윙스 발열내의|성수점 앞"),
        ("교보문고 한글날 컬렉션", r"교보|불면증 독서"),
        ("대구 동성로 2호점 개점", r"동성로.{0,12}2호점|동성로에 두 번째|동성로에 384평|동성로에 대형"),
        ("영등포 타임스퀘어점 리뉴얼", r"타임스퀘어"),
        ("성수 스파오프렌즈 랩 개점", r"스파오 ?프렌즈 랩|콜라보 실험실|성수동 첫 매장"),
        ("스파오키즈 새학기 페스타", r"새학기|신학기|스새페|등교룩"),
        ("스파오키즈 IP 협업 실내복", r"실내복|라운지웨어"),
        ("스윙스 웜테크 캠페인", r"웜테크|스윙스"),
        ("경량패딩 조기 출시", r"앞당겨|앞당겼|일찍 선보|먼저 출시|빠른 8월"),
        ("야장 윈드브레이커 추천", r"윈드브레이커"),
        ("헤럴드경제 SPA 키즈 패딩 기사", r"등골브레이커는 옛말|9만원대 SPA 패딩"),
    ],
    "탑텐": [
        ("텐텐데이 사흘 매출 309억", r"309억|300억"),
        ("하반기 텐텐데이 개막·할인", r"텐텐데이|텐텐\(10·10\)데이"),
        ("탑텐 2.0 대구 동성로점 리뉴얼", r"동성로|탑텐 ?2\.0"),
        ("탑텐키즈 론칭 10주년 캠페인", r"10주년|나는 너를 응원"),
        ("탑텐키즈 영유아 부모 설문", r"바디수트|첫 옷|브랜드 필름"),
        ("원가 상승에도 가격 동결·소싱 효율화", r"원가|소싱|가격 방어|생산 효율|생산 역량"),
        ("탑텐키즈 월계점·베이비 라인 성과", r"월계점|베이비|영패밀리|3040 가족"),
        ("국가대표 응원 캠페인", r"응원 캠페인|국가대표|국대|TOGETHER|응원 마케팅|응원 프로모션|온라인 응원"),
        ("메리노 스웨터 기획전", r"메리노|매출 24%"),
        ("이마트 신제주점 리뉴얼", r"신제주"),
        ("전지현 겨울 캠페인", r"WINTER|LIVE YOUR FLOW|(겨울|윈터).{0,12}캠페인|캠페인.{0,12}겨울|전지현 캠페인"),
        ("전지현 가을 캠페인", r"FALL|LIVE THE DAY|가을 캠페인|전지현"),
        ("체험형 매장·줄자 사이즈 측정",
         r"줄자|사이즈 측정|체험 매장|체험형 서비스|체험 콘텐츠|고객 경험 강화|재고 진단|매장의 귀환|오프라인 승부수|매장 CX"),
        ("서울 메트로 컬렉션", r"서울 ?메트로"),
        ("쿨에어 냉감 라인 판매 증가", r"쿨에어|냉감"),
        ("탑텐키즈 플러피플리스 확대", r"(?=.*탑텐키즈)(?=.*플리스)"),
        ("탑텐 플러피플리스 판매 호조", r"플러피|뽀글이"),
        ("에어테크 신제품 출시", r"에어테크"),
        ("헤럴드경제 SPA 키즈 패딩 기사", r"등골브레이커는 옛말|9만원대 SPA 패딩"),
    ],
}
SIMILAR = 0.45  # 그룹 밖 기사끼리 제목 2-gram 유사도가 이 이상이면 같은 보도로 묶음
DESC_SIMILAR = 0.3  # 또는 3일 이내 기사끼리 제목+요약 단어 겹침(작은 쪽 기준) 비율이 이 이상이면 같은 보도


def judge(r):
    brand, title, desc = r["brand"], r["title"], r["description"]
    text = f"{title} {desc}"
    stripped = re.sub(HOMONYMS[brand], "", text)
    if brand not in stripped:
        return "무관", "동음이의어: 브랜드가 아닌 다른 고유명사"
    in_title = brand in re.sub(HOMONYMS[brand], "", title)
    for verdict, pat, reason, always in RULES:
        if (always or not in_title) and re.search(pat, text if always else title + " " + desc):
            return verdict, reason
    if in_title:
        return "관련", "제목에 브랜드가 나오는 기사"
    if re.search(OTHER_BRANDS[brand], title):
        return "애매-제외", "다른 SPA 브랜드가 주제인 기사, 경쟁사로 언급"
    for pat, reason in TITLE_EXCLUDES:
        if re.search(pat, title):
            return "애매-제외", reason
    if stripped.count(brand) >= 2:
        return "애매-유지", "제목엔 없지만 요약에서 브랜드를 2회 이상 구체적으로 다룸"
    return "애매-제외", "요약에서 브랜드를 1회 나열·비교 수준으로만 언급"


def bigrams(s):
    s = re.sub(r"[^가-힣A-Za-z0-9]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


STOP = {"유니클로", "스파오", "탑텐", "탑텐키즈", "스파오키즈", "신성통상", "이랜드월드", "이랜드", "브랜드", "SPA",
        "운영하는", "패션", "제조", "유통", "일괄", "일괄형", "있다", "밝혔다", "따르면", "업계에", "대표", "기자", "지난",
        "올해", "이번", "통해", "위해", "함께", "다양한", "가을", "겨울", "있는", "에서", "으로"}


def tokens(s):
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", s) if w not in STOP}


def overlap(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0


def days_apart(a, b):
    return abs((datetime.strptime(a, "%Y-%m-%d") - datetime.strptime(b, "%Y-%m-%d")).days)


def mark_dups(rows):
    groups = defaultdict(list)
    for r in rows:
        if r["verdict"] not in KEEP:
            continue
        for name, pat in EVENTS.get(r["brand"], []):
            if re.search(pat, r["title"] + " " + r["description"]):
                groups[(r["brand"], name)].append(r)
                break
    grouped = {id(r) for ms in groups.values() for r in ms}
    loose = defaultdict(list)
    for r in rows:
        if r["verdict"] in KEEP and id(r) not in grouped:
            loose[r["brand"]].append(r)
    for brand, rs in loose.items():
        rs.sort(key=lambda r: r["pubDate"])
        clusters = []
        for r in rs:
            b, d, day = bigrams(r["title"]), tokens(r["title"] + " " + r["description"]), r["pubDate"][:10]
            for c in clusters:
                if (jaccard(b, c["bg"]) >= SIMILAR or
                        (days_apart(day, c["day"]) <= 3 and overlap(d, c["dg"]) >= DESC_SIMILAR)):
                    c["ms"].append(r)
                    break
            else:
                clusters.append({"bg": b, "dg": d, "day": day, "ms": [r]})
        for c in clusters:
            if len(c["ms"]) > 1:
                groups[(brand, "유사 제목: " + c["ms"][0]["title"][:20])] = c["ms"]

    for (brand, name), ms in groups.items():
        # 대표 기사: 제목에 자기 브랜드만 나오는 가장 이른 기사 > 제목에 브랜드가 나오는 기사 > 가장 이른 기사
        titled = ([m for m in ms if brand in m["title"] and not re.search(OTHER_BRANDS[brand], m["title"])]
                  or [m for m in ms if brand in m["title"]])
        rep = min(titled or ms, key=lambda m: m["pubDate"])
        for m in ms:
            m["dup_group"] = name
            if m is rep:
                m["dup_count"] = len(ms)
            else:
                m["verdict"], m["reason"] = "중복", f"대표 기사: #{rep['rank']} {rep['title'][:25]}"


def main():
    src = OUT_DIR / sys.argv[1] if len(sys.argv) > 1 else max(
        (p for p in OUT_DIR.glob("naver_news_*.csv") if re.fullmatch(r"naver_news_\d{8}_\d{4}", p.stem)),
        key=lambda p: p.stem)
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    by_link = defaultdict(set)
    for r in rows:
        by_link[r["originallink"] or r["link"]].add(r["brand"])
    for r in rows:
        r["verdict"], r["reason"] = judge(r)
        r["cross_brand"] = ",".join(sorted(by_link[r["originallink"] or r["link"]] - {r["brand"]}))
        r["dup_group"], r["dup_count"], r["selected"] = "", 1, ""
    mark_dups(rows)

    clean = []
    for brand in dict.fromkeys(r["brand"] for r in rows):
        kept = sorted((r for r in rows if r["brand"] == brand and r["verdict"] in KEEP),
                      key=lambda r: r["pubDate"], reverse=True)[:TARGET]
        for r in kept:
            r["selected"] = "Y"
        clean += kept

    fields = list(rows[0].keys())
    write_csv(OUT_DIR / f"{src.stem}_review.csv", rows, fields)
    write_csv(OUT_DIR / f"{src.stem}_clean.csv", clean, fields)
    write_md(OUT_DIR / f"{src.stem}_clean.md", clean, src)
    report(rows, clean, src)


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_md(path, rows, src):
    esc = lambda s: s.replace("|", "\\|").replace("\n", " ")
    lines = [f"# 브랜드별 뉴스 정제본 (출처: {src.name}, 브랜드별 최신 {TARGET}건)", ""]
    for brand in dict.fromkeys(r["brand"] for r in rows):
        sub = [r for r in rows if r["brand"] == brand]
        lines += [f"## {brand} ({len(sub)}건, {sub[-1]['pubDate'][:10]} ~ {sub[0]['pubDate'][:10]})", "",
                  "| 날짜 | 제목 | 요약 | 원문 | 판정 | 동일 보도 |", "|---|---|---|---|---|---:|"]
        for r in sub:
            lines.append(f"| {r['pubDate']} | {esc(r['title'])} | {esc(r['description'])} | "
                         f"[원문]({r['originallink'] or r['link']}) | {r['verdict']} | {r['dup_count']} |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def report(rows, clean, src):
    for brand in dict.fromkeys(r["brand"] for r in rows):
        sub = [r for r in rows if r["brand"] == brand]
        sel = [r for r in clean if r["brand"] == brand]
        horizon = sel[-1]["pubDate"] if sel else ""
        window = [r for r in sub if r["pubDate"] >= horizon]  # 정제본이 덮는 기간의 수집 기사
        c = lambda v: sum(r["verdict"] == v for r in window)
        print(f"\n===== {brand}: 정제 {len(sel)}건 ({horizon[:10]} ~ {sel[0]['pubDate'][:10] if sel else ''}) "
              f"| 해당 기간 수집 {len(window)} → 관련 {c('관련')}, 애매-유지 {c('애매-유지')} / "
              f"제외: 애매 {c('애매-제외')}, 무관 {c('무관')}, 중복 {c('중복')} =====")
        for r in (r for r in window if r["verdict"] == "애매-유지"):
            print(f"  [애매-유지] {r['pubDate'][5:10]} {r['title'][:40]}")
        groups = defaultdict(list)
        for r in window:
            if r["dup_group"]:
                groups[r["dup_group"]].append(r)
        for name, ms in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(ms) > 1:
                print(f"  [중복] {name}: {len(ms)}건 → 1건")
    print(f"\n저장: {OUT_DIR}\\{src.stem}_review.csv / _clean.csv / _clean.md (정제 {len(clean)}건)")


if __name__ == "__main__":
    main()
