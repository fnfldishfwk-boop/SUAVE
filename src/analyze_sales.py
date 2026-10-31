"""Descriptive sales analysis; no source or preprocessing changes."""
from pathlib import Path
import json
import sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/tables/sales_analysis'
OUT.mkdir(exist_ok=True)
d=pd.read_csv(ROOT/'data/processed/retail_2009_2010_net_sales.csv',dtype={'Invoice':str,'StockCode':str,'Customer ID':str},parse_dates=['InvoiceDate'])
u=pd.read_csv(ROOT/'reports/tables/unmatched_adjustments.csv',dtype={'Invoice':str,'StockCode':str,'Customer ID':str},parse_dates=['InvoiceDate'])
d['month']=d.InvoiceDate.dt.strftime('%Y-%m')
u['month']=u.InvoiceDate.dt.strftime('%Y-%m')
def export(frame,name):
    frame.to_csv(OUT/f'{name}.csv',encoding='utf-8-sig',index=True)
def summary(keys):
    x=d.groupby(keys,dropna=False).agg(retained_sales=('net_amount','sum'),net_units=('net_quantity','sum'),orders=('Invoice','nunique'),rows=('Invoice','size'))
    adj=u.groupby(keys,dropna=False).unmatched_amount.sum()
    x=x.join(adj.rename('unmatched_adjustment'),how='outer').fillna(0)
    x['reconciled_sales']=x.retained_sales+x.unmatched_adjustment
    x['retained_sales_per_order']=x.retained_sales/x.orders.replace(0,float('nan'))
    return x.sort_values('reconciled_sales',ascending=False)

univ=d[['net_quantity','Price','net_amount','returned_quantity']].describe(percentiles=[.5,.9,.95,.99,.999])
export(univ,'univariate_numeric')
monthly=summary('month').sort_index(); export(monthly,'monthly')
country=summary('Country'); export(country,'country')
membership=summary('customer_type'); export(membership,'membership')
product=summary('StockCode'); export(product,'products')
export(summary(['month','customer_type']),'month_membership')
export(summary(['Country','customer_type']),'country_membership')
export(summary(['month','Country']),'month_country')
orders=d.groupby('Invoice').agg(sales=('net_amount','sum'),units=('net_quantity','sum'),lines=('Invoice','size'),customer_types=('customer_type','nunique'),countries=('Country','nunique'))
export(orders.describe(percentiles=[.5,.9,.95,.99,.999]),'order_distribution')
members=d[d['Customer ID'].notna()]
customers=members.groupby('Customer ID').agg(sales=('net_amount','sum'),orders=('Invoice','nunique'),first=('InvoiceDate','min'),last=('InvoiceDate','max'))
ca=u[u['Customer ID'].notna()].groupby('Customer ID').unmatched_amount.sum()
customers=customers.join(ca.rename('unmatched_adjustment'),how='outer')
customers['reconciled_sales']=customers.sales.fillna(0)+customers.unmatched_adjustment.fillna(0)
customers=customers.sort_values('reconciled_sales',ascending=False); export(customers,'member_customers')
d['bulk_original_gt576']=d.original_quantity.gt(576)
bulk=summary('bulk_original_gt576') if False else d.groupby('bulk_original_gt576').agg(sales=('net_amount','sum'),rows=('Invoice','size'),orders=('Invoice','nunique'),units=('net_quantity','sum'))
export(bulk,'bulk_sensitivity')
# Original signed product ledger for occurrence-month checks (same preprocessing scope).
ledger=pd.read_pickle(ROOT/'data/interim/retail_filtered_pending_netting.pkl')
ledger['month']=ledger.InvoiceDate.dt.strftime('%Y-%m')
ledger['positive_sales']=ledger.line_amount.clip(lower=0)
ledger['return_magnitude']=-ledger.line_amount.clip(upper=0)
occ=ledger.groupby('month').agg(signed_sales=('line_amount','sum'),positive_sales=('positive_sales','sum'),return_magnitude=('return_magnitude','sum'))
export(occ,'occurrence_month_validation')
export(ledger.groupby('StockCode').agg(positive_sales=('positive_sales','sum'),return_magnitude=('return_magnitude','sum')).assign(return_amount_ratio=lambda x:x.return_magnitude/x.positive_sales.replace(0,float('nan'))).sort_values('return_magnitude',ascending=False),'product_returns')
corr=d[['net_quantity','Price','net_amount']].corr(method='spearman'); export(corr,'spearman_correlations')
full=float(d.net_amount.sum()+u.unmatched_amount.sum())
facts={'retained_sales':float(d.net_amount.sum()),'full_sales':full,'unmatched':float(u.unmatched_amount.sum()),'orders':len(orders),'products':len(product),'countries':len(country),'member_customers_with_purchase':int(members['Customer ID'].nunique()),'order_median':float(orders.sales.median()),'order_mean':float(orders.sales.mean()),'top10_product_share':float(product.reconciled_sales.head(10).sum()/full),'top10_country_share':float(country.reconciled_sales.head(10).sum()/full),'member_top10_share':float(customers.reconciled_sales.head(10).sum()/customers.reconciled_sales.sum()),'member_repeat_customer_share':float(customers.orders.fillna(0).gt(1).sum()/members['Customer ID'].nunique()),'member_repeat_sales_share':float(customers.loc[customers.orders.gt(1),'reconciled_sales'].sum()/customers.reconciled_sales.sum()),'invoices_mixed_type':int(orders.customer_types.gt(1).sum()),'invoices_mixed_country':int(orders.countries.gt(1).sum()),'spearman':corr.to_dict()}
(OUT/'facts.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(facts,ensure_ascii=False,indent=2))
for name,x in [('monthly',monthly),('country',country.head(8)),('membership',membership),('products',product.head(10)),('bulk',bulk),('occurrence',occ),('returns',ledger.groupby('StockCode').return_magnitude.sum().nlargest(5))]:
    print(name); print(x.to_string())
