# CLAUDE.md

프로젝트 구조와 일반 원칙은 `README.md`를 따릅니다. 아래는 추가 규칙입니다.

## 데이터 저장 위치

- API 등으로 **수집해서 정리한 데이터는 모두 `data/processed/` 안에 저장**합니다. `data/raw/`는 외부에서 받은 원본 파일(예: `online_retail_II.xlsx`)만 둡니다.
- 수집 소스별로 하위 폴더를 만듭니다. 네이버 뉴스는 `data/processed/naver_news/`입니다.
- 파일 이름에는 수집 시각을 붙입니다: `naver_news_YYYYMMDD_HHMM.csv`. 이 시각을 기준으로 파생 파일(`_review.csv`, `_clean.csv`, `.md` 표)을 같은 폴더에 둡니다.
- 기존 파일은 덮어쓰지 않고 새 시각으로 저장합니다.

## 네이버 API HUB

- 키는 `.env`의 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`에서 읽습니다. `.env`는 Git 추적 대상이 아니며, 키 값을 코드·문서·출력에 남기지 않습니다.
- 수집과 연동 테스트는 `src/naver_api_hub.py`(`news`, `test` 명령)를 사용합니다.
- 이미지·오타 변환·성인 검색어 판별 API는 현재 애플리케이션에서 활성화되어 있지 않습니다(HTTP 401).

## 뉴스 정제 규칙

`src/review_news.py`가 수집 CSV에 판정을 붙여 `_review.csv`(전체+판정)와 `_clean.csv`(브랜드별 최신 50건)를 만듭니다.
판정은 키워드 규칙(`HOMONYMS`, `RULES`, `TITLE_EXCLUDES`, `EVENTS`)으로 하므로 새로 수집한 파일에도 그대로 적용되며,
새 이슈·동음이의어가 보이면 규칙을 보강합니다. 정제 후 50건이 안 되면 `news --n 1000`까지 늘려 다시 수집합니다.

- **관련**: 브랜드가 기사 주제이거나, 브랜드의 상품·가격·매출·전략에 대한 구체적 내용이 있음 → 유지
- **애매-유지**: 주제는 다르지만 브랜드에 대한 구체적 정보가 있음 → 유지
- **애매-제외**: 브랜드가 나열·비유·경쟁사 언급 수준으로만 나옴 → 제외
- **무관**: 동음이의어(예: '탑텐가요쇼', '탑텐 텐아시아')나 다른 주제에서 지나가듯 언급 → 제외
- **중복**: 같은 사건을 여러 매체가 보도한 경우 그룹으로 묶고 대표 기사 1건만 남깁니다(기본은 가장 이른 기사). 대표 기사의 `dup_count`에 그룹 기사 수를 기록합니다.
- 같은 기사가 여러 브랜드 검색에 함께 잡히면, 각 브랜드에 대해 관련성을 따로 판정합니다(`cross_brand` 컬럼에 표시).
- 제목에 자기 브랜드가 없으면 요약문 언급 횟수로 나눕니다: 2회 이상 애매-유지, 1회 애매-제외.
- 대표 기사는 제목에 자기 브랜드만 나오는 가장 이른 기사를 우선합니다.

## 분석 결과물

- 집계는 `src/analyze_news.py <수집 stem>`으로 만듭니다. 집계표 CSV는 `reports/tables/news/`, 표 모음은 `reports/news_analysis_tables.md`에 저장됩니다.
- 주제 분류(제품 출시/협업/할인·행사/실적·사업/기타, 기사당 1개)는 `src/classify_news.py <수집 stem>`으로 만들며,
  `data/processed/naver_news/<stem>_category.csv`와 `reports/brand_news_categories.md`에 저장됩니다.
- 브랜드×주제별 키워드(BoW, TF-IDF)와 워드 클라우드는 `src/news_keywords.py <수집 stem>`으로 만듭니다.
  외부 라이브러리 없이 동작하며, 워드 클라우드는 `reports/figures/news_wordcloud/`(SVG + index.html)에 저장됩니다.
- 브랜드 검색 추이(데이터랩 검색어 트렌드·쇼핑인사이트)는 `src/search_trend.py`로 수집·시각화합니다.
  데이터는 `data/processed/naver_datalab/`, 차트는 `reports/search_trend_report.html`, 해석은 `reports/search_trend_analysis.md`.
  데이터랩 값은 호출마다 최댓값 100 기준이므로 다른 호출끼리는 점유율·분포로만 비교합니다.
- 대시보드: `.venv\Scripts\streamlit run src/dashboard.py` (가상환경 `.venv`, 패키지는 `requirements.txt`).
  뉴스·키워드·데이터랩 결과 파일을 읽기만 하므로, 분석을 다시 돌리면 새로고침으로 반영됩니다. 수집 파일 stem은 `STEM` 상수.
- 해석을 담은 보고서는 `reports/brand_news_analysis.md`이며, 표를 다시 만들면 보고서의 수치도 맞춰 갱신합니다.
