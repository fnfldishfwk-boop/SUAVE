"""SPA 3사(유니클로·스파오·탑텐) 뉴스·검색 분석 대시보드.

실행 (폴더2 에서):
    .venv\\Scripts\\streamlit run src/dashboard.py
필요 데이터: src/review_news.py, classify_news.py, news_keywords.py, search_trend.py 실행 결과
"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
NEWS = ROOT / "data" / "processed" / "naver_news"
LAB = ROOT / "data" / "processed" / "naver_datalab"
CLOUD = ROOT / "reports" / "figures" / "news_wordcloud"
STEM = "naver_news_20261031_1034"
BRANDS = ["유니클로", "스파오", "탑텐"]
COLORS = ["#d6312b", "#1f5fa8", "#2e8b57"]
BRAND_SCALE = alt.Scale(domain=BRANDS, range=COLORS)
CATEGORIES = ["제품 출시", "협업", "할인·행사", "실적·사업", "기타"]
AGES = ["10대", "20대", "30대", "40대", "50대", "60대+"]
RECENT = "2025-11"

st.set_page_config(page_title="SPA 3사 분석 대시보드", page_icon="📊", layout="wide")


@st.cache_data
def load():
    csv = lambda p: pd.read_csv(p, encoding="utf-8-sig")
    d = {
        "category": csv(NEWS / f"{STEM}_category.csv"),
        "review": csv(NEWS / f"{STEM}_review.csv"),
        "keywords": csv(ROOT / "reports" / "tables" / "news" / f"{STEM}_keywords.csv"),
        "monthly": csv(LAB / "monthly.csv"),
        "by_age": csv(LAB / "monthly_by_age.csv"),
        "gender": csv(LAB / "recent_by_gender.csv"),
        "device": csv(LAB / "recent_by_device.csv"),
        "shop_age": csv(LAB / "shop_age.csv"),
        "shop_gender": csv(LAB / "shop_gender.csv"),
        "shop_device": csv(LAB / "shop_device.csv"),
    }
    d["category"]["date"] = pd.to_datetime(d["category"]["pubDate"].str[:10])
    d["review"]["date"] = pd.to_datetime(d["review"]["pubDate"].str[:10])
    return d


def share(df, key):
    """그룹(key)·월 단위가 아닌 그룹 단위로 3사 점유율(%)."""
    g = df.groupby([key, "brand"])["ratio"].sum().reset_index()
    g["share"] = g["ratio"] / g.groupby(key)["ratio"].transform("sum") * 100
    return g


def dist(df, mapping):
    g = df.groupby(["brand", "group"])["ratio"].sum().reset_index()
    g["group"] = g["group"].astype(str).map(mapping).fillna(g["group"].astype(str))
    g["share"] = g["ratio"] / g.groupby("brand")["ratio"].transform("sum") * 100
    return g


def brand_color():
    return alt.Color("brand:N", scale=BRAND_SCALE, title="브랜드")


d = load()
st.title("SPA 3사 분석 대시보드: 유니클로 · 스파오 · 탑텐")
st.caption("출처: 네이버 뉴스 검색 API(브랜드별 정제 50건), 네이버 데이터랩 검색어 트렌드·쇼핑인사이트(2024-01 ~ 2026-10)")

with st.sidebar:
    st.header("필터")
    sel_brands = st.multiselect("브랜드", BRANDS, default=BRANDS)
    sel_cats = st.multiselect("뉴스 주제", CATEGORIES, default=CATEGORIES)
    st.divider()
    st.caption("데이터랩 값은 조회마다 최댓값 100 기준의 상대 지수입니다. 연령·성별·기기는 3사 점유율로 비교합니다.")
if not sel_brands:
    st.warning("브랜드를 하나 이상 선택하세요.")
    st.stop()

# ---------- KPI ----------
m = d["monthly"]
months = sorted(m["month"].unique())
last12, prev12 = months[-12:], months[-24:-12]
cols = st.columns(len(sel_brands))
tot12 = m[m["month"].isin(last12)]["ratio"].sum()
for col, b in zip(cols, sel_brands):
    mb = m[m["brand"] == b]
    cur, prev = mb[mb["month"].isin(last12)]["ratio"].sum(), mb[mb["month"].isin(prev12)]["ratio"].sum()
    news = d["category"][d["category"]["brand"] == b]
    with col:
        st.subheader(b)
        c1, c2, c3 = st.columns(3)
        c1.metric("검색 점유율(12개월)", f"{cur / tot12 * 100:.0f}%")
        c2.metric("검색량 전년비", f"{(cur / prev - 1) * 100:+.0f}%")
        c3.metric("뉴스 보도량", f"{news['dup_count'].sum():,}건", help="정제 50건의 동일 보도 수 합")

tab_search, tab_news, tab_kw, tab_quality = st.tabs(["🔍 검색 추이", "📰 뉴스 이슈", "🔑 키워드", "🧹 데이터 정제"])

# ---------- 검색 추이 ----------
with tab_search:
    mm = m[m["brand"].isin(sel_brands)].copy()
    mm["share"] = mm["ratio"] / m.groupby("month")["ratio"].transform("sum").reindex(mm.index) * 100
    left, right = st.columns(2)
    with left:
        st.markdown("**월별 검색량 지수** (3사 동시 조회, 최댓값=100)")
        st.altair_chart(alt.Chart(mm).mark_line(point=True).encode(
            x=alt.X("month:N", title=None), y=alt.Y("ratio:Q", title="지수"), color=brand_color(),
            tooltip=["brand", "month", alt.Tooltip("ratio:Q", format=".1f")]), width="stretch")
    with right:
        st.markdown("**월별 검색 점유율** (3사 합 = 100%)")
        st.altair_chart(alt.Chart(mm).mark_area(opacity=0.85).encode(
            x=alt.X("month:N", title=None), y=alt.Y("share:Q", title="%", stack=True), color=brand_color(),
            tooltip=["brand", "month", alt.Tooltip("share:Q", format=".1f")]), width="stretch")

    st.markdown(f"**연령대별 3사 검색 점유율** ({RECENT} ~ 최근)")
    age = share(d["by_age"][d["by_age"]["month"] >= RECENT], "age")
    age = age[age["brand"].isin(sel_brands)]
    st.altair_chart(alt.Chart(age).mark_bar().encode(
        x=alt.X("age:N", sort=AGES, title=None), xOffset="brand:N", y=alt.Y("share:Q", title="%"),
        color=brand_color(), tooltip=["age", "brand", alt.Tooltip("share:Q", format=".1f")]).properties(height=320),
        width="stretch")

    st.markdown("**연령대별 점유율 월간 추이**")
    ba = d["by_age"].copy()
    ba["share"] = ba["ratio"] / ba.groupby(["age", "month"])["ratio"].transform("sum") * 100
    ba = ba[ba["brand"].isin(sel_brands)]
    st.altair_chart(alt.Chart(ba).mark_line().encode(
        x=alt.X("month:N", title=None, axis=alt.Axis(labels=False, ticks=False)), y=alt.Y("share:Q", title="%"),
        color=brand_color(), tooltip=["age", "brand", "month", alt.Tooltip("share:Q", format=".1f")]
    ).properties(width=300, height=160).facet(facet=alt.Facet("age:N", sort=AGES, title=None), columns=3))

    l2, r2 = st.columns(2)
    with l2:
        st.markdown("**성별·기기별 3사 검색 점유율** (최근 12개월)")
        gd = pd.concat([share(d["gender"], "gender").rename(columns={"gender": "구분"}),
                        share(d["device"], "device").rename(columns={"device": "구분"})])
        gd = gd[gd["brand"].isin(sel_brands)]
        st.altair_chart(alt.Chart(gd).mark_bar().encode(
            x=alt.X("구분:N", sort=["여성", "남성", "모바일", "PC"], title=None), xOffset="brand:N",
            y=alt.Y("share:Q", title="%"), color=brand_color(),
            tooltip=["구분", "brand", alt.Tooltip("share:Q", format=".1f")]), width="stretch")
    with r2:
        st.markdown("**쇼핑 클릭 연령 분포** (패션의류 분야, 브랜드별 100%)")
        sa = dist(d["shop_age"], {"10": "10대", "20": "20대", "30": "30대", "40": "40대", "50": "50대", "60": "60대+"})
        sa = sa[sa["brand"].isin(sel_brands)]
        st.altair_chart(alt.Chart(sa).mark_bar().encode(
            y=alt.Y("brand:N", sort=BRANDS, title=None), x=alt.X("share:Q", title="%", stack="normalize"),
            color=alt.Color("group:N", sort=AGES, title="연령", scale=alt.Scale(scheme="orangered")),
            order=alt.Order("group:N"), tooltip=["brand", "group", alt.Tooltip("share:Q", format=".1f")]),
            width="stretch")
        sg = pd.concat([dist(d["shop_gender"], {"f": "여성", "m": "남성"}),
                        dist(d["shop_device"], {"mo": "모바일", "pc": "PC"})])
        sg = sg[sg["brand"].isin(sel_brands)]
        st.dataframe(sg.pivot_table(index="brand", columns="group", values="share").round(1)
                     .reindex(columns=["여성", "남성", "모바일", "PC"]), width="stretch")
    st.info("나이가 어릴수록 스파오, 많을수록 유니클로 점유율이 높습니다. 탑텐은 30~40대가 핵심이고, "
            "텐텐데이가 열리는 10월마다 점유율이 크게 오릅니다. 자세한 해석: reports/search_trend_analysis.md")

# ---------- 뉴스 ----------
with tab_news:
    cat = d["category"]
    cat = cat[cat["brand"].isin(sel_brands) & cat["category"].isin(sel_cats)]
    l, r = st.columns(2)
    with l:
        st.markdown("**브랜드별 뉴스 주제 분포** (정제 기사 수)")
        st.altair_chart(alt.Chart(cat).mark_bar().encode(
            y=alt.Y("brand:N", sort=BRANDS, title=None), x=alt.X("count():Q", title="기사 수", stack="normalize"),
            color=alt.Color("category:N", sort=CATEGORIES, title="주제", scale=alt.Scale(scheme="tableau10")),
            tooltip=["brand", "category", "count()"]), width="stretch")
    with r:
        st.markdown("**주별 보도량** (동일 보도 포함)")
        wk = cat.assign(week=cat["date"].dt.to_period("W").dt.start_time)
        st.altair_chart(alt.Chart(wk).mark_bar().encode(
            x=alt.X("week:T", title=None), y=alt.Y("sum(dup_count):Q", title="보도량"), color=brand_color(),
            tooltip=["brand", "week:T", "sum(dup_count):Q"]), width="stretch")

    st.markdown("**주요 이슈** (동일 보도 수 상위)")
    top = cat.sort_values("dup_count", ascending=False).groupby("brand").head(8)
    st.dataframe(top[["brand", "category", "pubDate", "title", "dup_count", "originallink"]].rename(columns={
        "brand": "브랜드", "category": "주제", "pubDate": "날짜", "title": "제목", "dup_count": "동일 보도",
        "originallink": "원문"}), width="stretch", hide_index=True,
        column_config={"원문": st.column_config.LinkColumn("원문", display_text="열기")})

    with st.expander(f"정제 기사 전체 ({len(cat)}건)"):
        q = st.text_input("제목 검색")
        view = cat[cat["title"].str.contains(q, case=False, na=False)] if q else cat
        st.dataframe(view[["brand", "category", "pubDate", "title", "description", "dup_count", "originallink"]],
                     width="stretch", hide_index=True,
                     column_config={"originallink": st.column_config.LinkColumn("원문", display_text="열기")})

# ---------- 키워드 ----------
with tab_kw:
    kw = d["keywords"]
    c1, c2 = st.columns(2)
    b = c1.selectbox("브랜드", sel_brands)
    avail = [c for c in CATEGORIES if c in kw[kw["brand"] == b]["category"].unique()]
    c = c2.selectbox("주제", avail)
    sub = kw[(kw["brand"] == b) & (kw["category"] == c)]
    n = int(sub["articles"].iloc[0])
    if n < 5:
        st.warning(f"기사 {n}건이라 키워드는 참고용입니다.")
    bow_set, tf_set = set(sub["bow_term"]), set(sub["tfidf_term"])
    st.markdown(f"공통 **{len(bow_set & tf_set)}개** · BoW에만: {', '.join(sorted(bow_set - tf_set)) or '없음'} · "
                f"TF-IDF에만: {', '.join(sorted(tf_set - bow_set)) or '없음'}")
    l, r = st.columns(2)
    for col, term, val, title in ((l, "bow_term", "bow_count", "BoW (빈도)"), (r, "tfidf_term", "tfidf_score", "TF-IDF")):
        with col:
            st.markdown(f"**{title}**")
            fn = CLOUD / f"{b}_{c.replace('·', '-')}_{'bow' if term == 'bow_term' else 'tfidf'}.svg"
            if fn.exists():
                st.markdown(f'<div style="border:1px solid #e3e6ea;border-radius:6px">{fn.read_text(encoding="utf-8")}</div>',
                            unsafe_allow_html=True)
            st.altair_chart(alt.Chart(sub).mark_bar(color=COLORS[BRANDS.index(b)]).encode(
                y=alt.Y(f"{term}:N", sort="-x", title=None), x=alt.X(f"{val}:Q", title=None),
                tooltip=[term, val]).properties(height=360), width="stretch")

# ---------- 정제 ----------
with tab_quality:
    rv = d["review"]
    rv = rv[rv["brand"].isin(sel_brands)]
    st.markdown("**수집 3,000건의 판정 결과**")
    order = ["관련", "애매-유지", "애매-제외", "무관", "중복"]
    st.altair_chart(alt.Chart(rv).mark_bar().encode(
        y=alt.Y("brand:N", sort=BRANDS, title=None), x=alt.X("count():Q", title="기사 수"),
        color=alt.Color("verdict:N", sort=order, title="판정",
                        scale=alt.Scale(domain=order, range=["#2e8b57", "#8bc34a", "#f0ad4e", "#d9534f", "#9e9e9e"])),
        tooltip=["brand", "verdict", "count()"]), width="stretch")
    reasons = (rv[rv["verdict"].isin(["무관", "애매-제외"])].groupby(["brand", "verdict", "reason"]).size()
               .reset_index(name="건수").sort_values("건수", ascending=False))
    st.markdown("**제외 사유 상위**")
    st.dataframe(reasons.head(20), width="stretch", hide_index=True)
    st.caption("판정 규칙: src/review_news.py, 기준 설명: CLAUDE.md '뉴스 정제 규칙'")
