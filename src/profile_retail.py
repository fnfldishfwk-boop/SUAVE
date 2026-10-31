"""Read-only source profiling and a reviewable preprocessing candidate."""
from pathlib import Path
import json
import re
import sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_excel(ROOT / 'data/raw/online_retail_II.xlsx', sheet_name='Year 2009-2010', dtype={'Invoice': str, 'StockCode': str, 'Customer ID': str})
stats = {'raw_rows': len(df), 'exact_duplicate_rows': int(df.duplicated().sum())}
df = df.drop_duplicates().copy()
df['Description'] = df['Description'].str.strip().replace('', pd.NA)
df['StockCode'] = df['StockCode'].str.strip()
# Do not choose a name silently where a code has multiple descriptions.
names = df.dropna(subset=['Description']).groupby('StockCode')['Description'].agg(lambda s: sorted(set(s)))
mapping = names[names.map(len).eq(1)].map(lambda x: x[0])
missing_before = int(df['Description'].isna().sum())
df['Description'] = df['Description'].fillna(df['StockCode'].map(mapping))
stats['description_missing_before'] = missing_before
stats['description_filled'] = missing_before - int(df['Description'].isna().sum())
stats['description_missing_after'] = int(df['Description'].isna().sum())
df['customer_type'] = df['Customer ID'].notna().map({True: '회원', False: '비회원'})
df['line_amount'] = df['Quantity'] * df['Price']
stats['nonpositive_price_rows'] = int(df['Price'].le(0).sum())
stats['nonpositive_quantity_rows'] = int(df['Quantity'].le(0).sum())
stats['negative_amount_rows'] = int(df['line_amount'].lt(0).sum())
stats['post_dedup_amount'] = float(df['line_amount'].sum())
codes = df.groupby('StockCode').agg(rows=('Invoice','size'), description=('Description',lambda x: ' | '.join(x.dropna().unique()[:5])), min_quantity=('Quantity','min'), max_quantity=('Quantity','max'), amount=('line_amount','sum')).reset_index()
unusual = codes[~codes['StockCode'].str.fullmatch(r'\d{5}[A-Za-z]*')]
unusual.to_csv(ROOT / 'reports/tables/unusual_codes_review.csv', index=False, encoding='utf-8-sig')
# Large-order review only: no automatic removal of valid bulk orders.
positive = df[df['Quantity'].gt(0) & df['Price'].gt(0)]
q1, q3 = positive['Quantity'].quantile([.25,.75])
threshold = float(q3 + 1.5*(q3-q1))
stats['quantity_review'] = {'q1':float(q1),'q3':float(q3),'iqr_upper':threshold,'p99':float(positive['Quantity'].quantile(.99)), 'flagged_rows':int(positive['Quantity'].gt(threshold).sum())}
sample = positive.sort_values(['Quantity','line_amount'],ascending=False).head(30)
sample.to_csv(ROOT / 'reports/tables/bulk_order_samples.csv',index=False,encoding='utf-8-sig')
df.to_pickle(ROOT / 'data/interim/retail_preprocessing_candidate.pkl')
(ROOT / 'reports/tables/preprocessing_profile.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(stats,ensure_ascii=False,indent=2))
print('UNUSUAL CODES')
print(unusual.to_json(orient='records',force_ascii=False))
print('BULK SAMPLES')
print(sample.head(10).to_json(orient='records',force_ascii=False,date_format='iso'))
