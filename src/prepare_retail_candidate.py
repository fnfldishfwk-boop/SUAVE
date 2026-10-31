"""Apply independent rules; netting and negative-value policy await clarification."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_pickle(ROOT / 'data/interim/retail_preprocessing_candidate.pkl')
excluded_codes = {'ADJUST','ADJUST2','AMAZONFEE','B','BANK CHARGES','C2','C3','D','DOT','GIFT','M','POST','S','TEST001','TEST002'}
code = df['StockCode'].str.upper()
excluded = code.isin(excluded_codes) | code.str.startswith('GIFT_')
audit = df.loc[excluded].groupby('StockCode').agg(rows=('Invoice','size'),signed_amount=('line_amount','sum')).reset_index()
audit.to_csv(ROOT / 'reports/tables/excluded_nonproduct_codes.csv',index=False,encoding='utf-8-sig')
candidate = df.loc[~excluded & df['Price'].ne(0) & df['Quantity'].ne(0)].copy()
# This is deliberately not a final net-sales dataset: signed entries are retained
# until the user confirms how to reconcile net sales and negative-row exclusion.
candidate.to_pickle(ROOT / 'data/interim/retail_filtered_pending_netting.pkl')
positive = candidate.loc[candidate['Quantity'].gt(0) & candidate['Price'].gt(0)]
q1,q3 = positive['Quantity'].quantile([.25,.75])
threshold = float(q3 + 1.5*(q3-q1))
sample = positive.sort_values(['Quantity','line_amount'],ascending=False).head(30)
sample.to_csv(ROOT / 'reports/tables/bulk_order_samples.csv',index=False,encoding='utf-8-sig')
summary = {'excluded_nonproduct_rows':int(excluded.sum()),'excluded_nonproduct_signed_amount':float(df.loc[excluded,'line_amount'].sum()),'pending_candidate_rows':len(candidate),'iqr_upper_quantity':threshold,'quantity_p99':float(positive['Quantity'].quantile(.99)),'bulk_review_rows':int(positive['Quantity'].gt(threshold).sum()),'status':'pending user clarification: net sales versus negative-row exclusion'}
(ROOT / 'reports/tables/preprocessing_pending_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
