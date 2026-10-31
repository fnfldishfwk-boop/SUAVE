# Online Retail 데이터 분석 프로젝트

## SPA 3사 뉴스·검색 분석 대시보드 (Streamlit)

- 로컬 실행: `pip install -r requirements.txt` 후 `streamlit run streamlit_app.py`
- Streamlit Community Cloud 배포: 이 저장소를 선택하고 Main file path를 `streamlit_app.py`로 지정합니다. API 키 없이 저장소에 포함된 결과 파일(`data/processed/naver_news`, `data/processed/naver_datalab`, `reports/tables/news`, `reports/figures/news_wordcloud`)만 읽습니다.
- 데이터를 새로 수집하려면 `.env`에 네이버 API HUB 키를 넣고 `src/naver_api_hub.py` → `review_news.py` → `classify_news.py` → `news_keywords.py` → `search_trend.py` 순으로 실행합니다. 자세한 규칙은 `CLAUDE.md`를 참고하세요.

## 폴더 구조

```text
.
├── data/
│   ├── raw/                 # 원본 데이터 (직접 수정하지 않음)
│   │   └── online_retail_II.xlsx
│   ├── interim/             # 전처리 중간 데이터
│   └── processed/           # 분석에 사용할 최종 정제 데이터
├── notebooks/              # 탐색적 분석 및 실험 노트북
├── src/                    # 재사용 가능한 로딩·전처리·분석 코드
├── reports/
│   ├── figures/            # 차트와 시각화 이미지
│   └── tables/             # 집계표 및 결과 데이터
├── docs/                   # 데이터 설명, 분석 계획, 의사결정 기록
├── config/                 # 경로·분석 옵션 등 설정
├── .gitignore
└── README.md
```

## 작업 원칙

- 원본 Excel 파일은 `data/raw/`에 보관하고, 가공 결과는 별도 파일로 저장합니다.
- 분석은 `data/raw → data/interim → data/processed → reports` 흐름으로 진행합니다.
- 노트북은 `01_data_overview.ipynb`, `02_data_cleaning.ipynb`, `03_analysis.ipynb`처럼 순서와 목적을 이름에 표시합니다.
- 반복해서 사용하는 코드는 `src/`로 옮깁니다.
- 분석 목적, 컬럼 정의, 결측치·중복·취소 거래 처리 기준 등은 `docs/`에 기록합니다.
- 최종 보고서는 `reports/`, 차트는 `reports/figures/`, 집계표는 `reports/tables/`에 저장합니다.
- 코드에서 사용하는 데이터 경로는 프로젝트 루트를 기준으로 관리합니다. 노트북의 실행 위치에 따라 상대 경로가 달라질 수 있습니다.

## 현재 상태

- 원본 데이터: `data/raw/online_retail_II.xlsx`
- 프로젝트 폴더 구성 완료. 데이터 분석과 개발 환경 설치는 아직 수행하지 않았습니다.
- 데이터와 생성 결과물은 기본적으로 Git 추적 대상에서 제외됩니다. 공유가 필요하면 `.gitignore`를 조정하세요.
- `.gitkeep`은 빈 폴더를 Git으로 유지하기 위한 파일입니다.
