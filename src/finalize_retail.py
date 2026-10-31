"""Net product returns against earlier purchases using an explicit matching rule."""
from pathlib import Path
from collections import defaultdict
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_pickle(ROOT / 'data/interim/retail_filtered_pending_netting.pkl').copy()
df['source_excel_row'] = df.index + 2
df = df.sort_values(['InvoiceDate','source_excel_row']).reset_index(drop=True)
df['net_quantity'] = df['Quantity'].clip(lower=0).astype(float)
df['returned_quantity'] = 0.0
stacks = defaultdict(list)
links, unresolved = [], []

for i, row in enumerate(df.itertuples(index=False, name=None)):
    r = df.iloc[i]
    customer = r['Customer ID']
    key = (customer, r['StockCode'], float(r['Price']), r['Country'])
    if r['Quantity'] > 0 and r['Price'] > 0 and not str(r['Invoice']).upper().startswith('C'):
        if pd.notna(customer):
            stacks[key].append(i)
        continue
    df.at[i, 'net_quantity'] = 0.0
    if r['Quantity'] < 0 and r['Price'] > 0:
        remaining = float(-r['Quantity'])
        reason = 'customer_missing' if pd.isna(customer) else 'no_earlier_matching_purchase'
        stack = stacks[key] if pd.notna(customer) else []
        while remaining > 0 and stack:
            sale_i = stack[-1]
            take = min(remaining, df.at[sale_i, 'net_quantity'])
            df.at[sale_i, 'net_quantity'] -= take
            df.at[sale_i, 'returned_quantity'] += take
            links.append({'sale_source_row':int(df.at[sale_i,'source_excel_row']),'return_source_row':int(r['source_excel_row']),'matched_quantity':take,'matched_amount':take*float(r['Price'])})
            remaining -= take
            if df.at[sale_i,'net_quantity'] == 0:
                stack.pop()
        if remaining:
            out = r.to_dict()
            out.update(unmatched_quantity=remaining,unmatched_amount=-remaining*float(r['Price']),reason=reason)
            unresolved.append(out)
    else:
        out = r.to_dict()
        out.update(unmatched_quantity=float(r['Quantity']),unmatched_amount=float(r['line_amount']),reason='negative_price_or_inconsistent_cancellation')
        unresolved.append(out)

df['net_amount'] = df['net_quantity']*df['Price']
final = df.loc[df['net_quantity'].gt(0) & df['net_amount'].gt(0) & df['Price'].gt(0)].copy()
final.rename(columns={'Quantity':'original_quantity','line_amount':'original_amount'},inplace=True)
unmatched = pd.DataFrame(unresolved)
matched_amount = sum(x['matched_amount'] for x in links)
unmatched_amount = sum(x['unmatched_amount'] for x in unresolved)
signed_total = float(df['line_amount'].sum())
final_total = float(final['net_amount'].sum())
assert math.isclose(final_total+unmatched_amount,signed_total,abs_tol=0.00001)
assert final['net_amount'].gt(0).all() and final['net_quantity'].gt(0).all()
assert final['Description'].dropna().eq(final['Description'].dropna().str.strip()).all()
final.to_csv(ROOT / 'data/processed/retail_2009_2010_net_sales.csv',index=False,encoding='utf-8-sig')
unmatched.to_csv(ROOT / 'reports/tables/unmatched_adjustments.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(links).to_csv(ROOT / 'reports/tables/return_matching_audit.csv',index=False,encoding='utf-8-sig')
summary = {'input_product_rows':len(df),'final_positive_rows':len(final),'final_positive_net_amount':final_total,'matched_return_amount':matched_amount,'unmatched_adjustment_rows':len(unresolved),'unmatched_signed_amount':unmatched_amount,'full_product_signed_net_amount':signed_total,'reconciliation_difference':final_total+unmatched_amount-signed_total,'description_missing_final':int(final['Description'].isna().sum()),'guest_rows_final':int(final['Customer ID'].isna().sum()),'matching_rule':'same known customer, stock code, exact price, country; most recent earlier purchase first; inferred, not verified original invoice link'}
pd.DataFrame([summary]).to_csv(ROOT / 'reports/tables/net_sales_summary.csv',index=False,encoding='utf-8-sig')
(ROOT / 'reports/tables/net_sales_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
