"""NAVER API HUB 연동 테스트 및 뉴스 수집 스크립트.

키는 프로젝트 루트(폴더2)의 .env 에서 읽습니다:
    NAVER_CLIENT_ID=...
    NAVER_CLIENT_SECRET=...

사용법 (폴더2 에서 실행):
    python src/naver_api_hub.py test            # 검색 API 10종 + 데이터랩(검색어트렌드/쇼핑인사이트) 9종 연동 테스트
    python src/naver_api_hub.py news            # 유니클로/스파오/탑텐 최신 뉴스 50개씩 수집
    python src/naver_api_hub.py news 나이키 아디다스 --n 30
"""
import argparse
import csv
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_URL = "https://naverapihub.apigw.ntruss.com"
ROOT = Path(__file__).resolve().parents[1]

# 문서 기준 검색 API 목록 (경로는 /search/v1/<name>)
SEARCH_APIS = {
    "news": "뉴스",
    "blog": "블로그",
    "cafearticle": "카페글",
    "kin": "지식iN",
    "webkr": "웹문서",
    "image": "이미지",
    "encyc": "백과사전",
    "local": "지역",
    "errata": "오타 변환",
    "adult": "성인 검색어 판별",
}

# 데이터랩 계열 POST API (검색어트렌드 / 쇼핑인사이트)
FASHION = "50000000"  # 네이버쇼핑 패션의류 cat_id
BRANDS = ["유니클로", "스파오", "탑텐"]
TREND_APIS = {
    "search-trend/v1/search": ("검색어 트렌드", lambda: {
        "keywordGroups": [{"groupName": b, "keywords": [b]} for b in BRANDS]}),
    "shopping/v1/categories": ("쇼핑 분야별 트렌드", lambda: {
        "category": [{"name": "패션의류", "param": [FASHION]},
                     {"name": "패션잡화", "param": ["50000001"]}]}),
    "shopping/v1/category/device": ("쇼핑 분야 기기별", lambda: {"category": FASHION}),
    "shopping/v1/category/gender": ("쇼핑 분야 성별", lambda: {"category": FASHION}),
    "shopping/v1/category/age": ("쇼핑 분야 연령별", lambda: {"category": FASHION}),
    "shopping/v1/category/keywords": ("쇼핑 키워드별 트렌드", lambda: {
        "category": FASHION, "keyword": [{"name": b, "param": [b]} for b in BRANDS]}),
    "shopping/v1/category/keyword/device": ("쇼핑 키워드 기기별", lambda: {
        "category": FASHION, "keyword": BRANDS[0]}),
    "shopping/v1/category/keyword/gender": ("쇼핑 키워드 성별", lambda: {
        "category": FASHION, "keyword": BRANDS[0]}),
    "shopping/v1/category/keyword/age": ("쇼핑 키워드 연령별", lambda: {
        "category": FASHION, "keyword": BRANDS[0]}),
}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_env():
    env_path = ROOT / ".env"
    if not env_path.exists():
        sys.exit(f".env 파일이 없습니다: {env_path}")
    env = {}
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    cid, secret = env.get("NAVER_CLIENT_ID"), env.get("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit(".env 에 NAVER_CLIENT_ID 와 NAVER_CLIENT_SECRET 을 모두 채워주세요.")
    return cid, secret


def call(api, params, cid, secret):
    return request(f"search/v1/{api}?{urllib.parse.urlencode(params)}", cid, secret)


def request(path, cid, secret, body=None):
    headers = {"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": secret}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body)
        except ValueError:
            pass
        return e.code, body


def clean(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def cmd_test(args, cid, secret):
    print(f"[연동 테스트] 검색어: {args.query}\n")
    for api, label in SEARCH_APIS.items():
        params = {"query": args.query}
        if api not in ("errata", "adult"):
            params["display"] = 3
        status, data = call(api, params, cid, secret)
        print(f"■ {label} ({api}) → HTTP {status}")
        if status != 200:
            print(f"   오류: {data}\n")
            continue
        if "items" in data:
            print(f"   total={data.get('total')}")
            for it in data["items"][:3]:
                print(f"   - {clean(it.get('title'))}  {it.get('link', '')}")
        else:
            print(f"   {data}")
        print()

    print(f"[데이터랩 테스트] 기간: {args.start} ~ {args.end} (월간)\n")
    for path, (label, extra) in TREND_APIS.items():
        body = {"startDate": args.start, "endDate": args.end, "timeUnit": "month", **extra()}
        status, data = request(path, cid, secret, body)
        print(f"■ {label} ({path}) → HTTP {status}")
        if status != 200:
            print(f"   오류: {data}\n")
            continue
        for r in data.get("results", []):
            series = r.get("data", [])
            name = r.get("title")
            # 기기/성별/연령 API 는 group 필드로 구분된 행이 섞여 옵니다
            groups = sorted({d.get("group") for d in series if d.get("group")})
            if groups:
                for g in groups:
                    pts = [d for d in series if d.get("group") == g]
                    print(f"   - {name}/{g}: " + ", ".join(f"{d['period'][:7]}={d['ratio']:.1f}" for d in pts))
            else:
                print(f"   - {name}: " + ", ".join(f"{d['period'][:7]}={d['ratio']:.1f}" for d in series))
        print()


def cmd_news(args, cid, secret):
    rows = []
    for brand in args.brands:
        got, start = [], 1
        while len(got) < args.n:
            display = min(100, args.n - len(got))
            status, data = call("news", {"query": brand, "display": display,
                                         "start": start, "sort": "date"}, cid, secret)
            if status != 200:
                print(f"[{brand}] HTTP {status}: {data}")
                break
            items = data.get("items", [])
            if not items:
                break
            got.extend(items)
            start += len(items)
        print(f"\n===== {brand}: {len(got)}건 =====")
        for i, it in enumerate(got, 1):
            pub = datetime.strptime(it["pubDate"], "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d %H:%M")
            row = {"brand": brand, "rank": i, "pubDate": pub, "title": clean(it["title"]),
                   "description": clean(it["description"]),
                   "originallink": it.get("originallink", ""), "link": it.get("link", "")}
            rows.append(row)
            print(f"{i:>2}. [{pub}] {row['title']}\n    {row['originallink'] or row['link']}")

    out_dir = ROOT / "data" / "processed" / "naver_news"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = out_dir / f"naver_news_{stamp}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["brand"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n저장: {csv_path} ({len(rows)}건)")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test")
    t.add_argument("--query", default="웰치스")
    t.add_argument("--start", default="2026-05-01")
    t.add_argument("--end", default="2026-10-30")
    n = sub.add_parser("news")
    n.add_argument("brands", nargs="*", default=["유니클로", "스파오", "탑텐"])
    n.add_argument("--n", type=int, default=50)
    args = p.parse_args()
    cid, secret = load_env()
    {"test": cmd_test, "news": cmd_news}[args.cmd](args, cid, secret)


if __name__ == "__main__":
    main()
