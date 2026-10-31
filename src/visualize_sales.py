from pathlib import Path
import json
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
DEST=Path('C:/Users/SuA/.codex/visualizations/2026/10/29/01a18763-48ba-7cf0-b5ad-7f4a2abe25f0')
d=pd.read_csv(ROOT/'data/processed/retail_2009_2010_net_sales.csv',dtype={'Invoice':str,'StockCode':str,'Customer ID':str})
T=ROOT/'reports/tables/sales_analysis'
template=(ROOT/'reports/figures/sales-chart-template.html').read_text(encoding='utf-8')
def bar(title,subtitle,labels,values,unit,axis):return dict(type='bar',title=title,subtitle=subtitle,labels=labels,values=[float(x) for x in values],unit=unit,axis=axis)
def bins(s,edges,labels):return pd.cut(s,edges,labels=labels,right=True,include_lowest=True).value_counts(sort=False).div(len(s)).mul(100).tolist()
def emit(name,charts):
    text=template.replace('ROOT_ID',name).replace('CHART_DATA',json.dumps(charts,ensure_ascii=False))
    assert len(text.encode('utf-8'))<1000000
    (DEST/f'{name}.html').write_text(text,encoding='utf-8')
    (ROOT/'reports/figures'/f'{name}-data.json').write_text(json.dumps(charts,ensure_ascii=False,indent=2),encoding='utf-8')
orders=d.groupby('Invoice').net_amount.sum()
emit('sales-distributions',[
 bar('상품 거래 행별 순수량 분포','최종 499,391행 · 대량 주문 포함 · 중앙값 3개 / 평균 11.26개',['1~3개','4~12개','13~24개','25~120개','120개 초과'],bins(d.net_quantity,[0,3,12,24,120,float('inf')],['a','b','c','d','e']),'%','전체 상품 거래 행 대비 비중 (%)'),
 bar('상품 거래 행별 단가 분포','중앙값 2.10 / 평균 3.42 · 원본 금액 단위',['1 이하','1 초과~3','3 초과~10','10 초과~30','30 초과'],bins(d.Price,[0,1,3,10,30,float('inf')],['a','b','c','d','e']),'%','전체 상품 거래 행 대비 비중 (%)'),
 bar('주문별 금액 분포','유지된 구매 전표 20,433개 · 중앙값 292.47 / 평균 469.57',['100 이하','100~300','300~500','500~1,000','1,000 초과'],bins(orders,[0,100,300,500,1000,float('inf')],['a','b','c','d','e']),'%','전체 유지 구매 주문 대비 비중 (%)')])
occ=pd.read_csv(T/'occurrence_month_validation.csv')
mm=pd.read_csv(T/'month_membership.csv').pivot(index='month',columns='customer_type',values='retained_sales_per_order').sort_index()
monthly=pd.read_csv(T/'monthly.csv')
emit('sales-time-membership',[
 dict(type='line',title='월별 상품 순매출',subtitle='거래 발생월 기준 · 음수 거래 전체 반영 · 마지막 12월은 9일까지',labels=occ.month.str.slice(2).tolist(),series=[dict(name='발생월 순매출',values=(occ.signed_sales/10000).tolist())],unit='만',axis='매출 (만 단위)',partialLast=True),
 dict(type='line',title='월별 구매 주문 수',subtitle='취소 차감 후 양수 금액이 남은 전표 · 완전 취소 주문 제외',labels=monthly.month.str.slice(2).tolist(),series=[dict(name='구매 주문',values=monthly.orders.tolist())],unit='건',axis='주문 수 (건)',partialLast=True),
 dict(type='line',title='회원·비회원 주문당 금액',subtitle='유지 거래 금액 ÷ 구매 주문 수 · 미연결 취소 미배분 · 12월 부분 기간',labels=[x[2:] for x in mm.index],series=[dict(name=x,values=mm[x].tolist()) for x in ['회원','비회원']],unit='',axis='주문당 금액',partialLast=True)])
country=pd.read_csv(T/'country.csv'); full=9557222.784
returnp=pd.read_csv(T/'product_returns.csv').head(5)
custom=pd.read_csv(T/'member_customers.csv');cs=custom.reconciled_sales.sum(); n=10
emit('sales-market-returns',[
 bar('국가별 상품 순매출 비중','동일 국가의 미연결 취소까지 반영',['영국','아일랜드','네덜란드','독일','프랑스','기타'],list(country.reconciled_sales.head(5)/full*100)+[float(country.reconciled_sales.iloc[5:].sum()/full*100)],'%','전체 상품 순매출 대비 비중 (%)'),
 bar('국가별 주문당 금액','유지 거래 기준 · 국가 간 상품·고객 구성이 다름',['영국','아일랜드','네덜란드','독일','프랑스','덴마크'],country.set_index('Country').loc[['United Kingdom','EIRE','Netherlands','Germany','France','Denmark'],'retained_sales_per_order'].tolist(),'','주문당 금액 (원본 단위)'),
 bar('취소·반품 금액이 큰 상품: 금액 비율','음수 금액 절댓값 상위 5개 · 같은 주문의 반품 확률이 아님',returnp.StockCode.astype(str).tolist(),returnp.return_amount_ratio*100,'%','기간 내 음수 금액 ÷ 양수 금액 (%)'),
 bar('회원 고객 매출 집중도','회원별 미연결 취소 포함 · 상위 10명 / 나머지 비교',['상위 10명','나머지 고객'],[custom.reconciled_sales.head(10).sum()/cs*100,custom.reconciled_sales.iloc[10:].sum()/cs*100],'%','회원 상품 순매출 대비 비중 (%)')])
print('Created 3 chart groups, 10 charts. All observations retained in bins/aggregates.')
