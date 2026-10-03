"""Turns the raw sales export into a small star schema (fact + 2 dims) for the Power BI report.
Input: sales_export.csv (May-Sep 2026), not included in the repo."""
import re, pandas as pd, numpy as np

SRC = 'sales_export.csv'  # raw export, not included in this repo
d = pd.read_csv(SRC)
d['sale_ts'] = pd.to_datetime(d['ts'], utc=True)
d['sale_date'] = d['sale_ts'].dt.date

# ---- dim_item -------------------------------------------------------------
CATS = {
 'Rifle': ['AK-47','M4A4','M4A1-S','AUG','SG 553','FAMAS','Galil AR'],
 'Sniper': ['AWP','SSG 08','SCAR-20','G3SG1'],
 'Pistol': ['Desert Eagle','USP-S','Glock-18','P250','Five-SeveN','Tec-9','CZ75-Auto','P2000','Dual Berettas','R8 Revolver'],
 'SMG': ['MP9','MAC-10','MP7','MP5-SD','UMP-45','P90','PP-Bizon'],
 'Heavy': ['Nova','XM1014','MAG-7','Sawed-Off','M249','Negev'],
}
W2C = {w: c for c, ws in CATS.items() for w in ws}
WEARS = ['Factory New','Minimal Wear','Field-Tested','Well-Worn','Battle-Scarred']

def parse(name):
    n = name
    stattrak = 'StatTrak™' in n
    souvenir = n.startswith('Souvenir ')
    star = n.startswith('★')
    wear = next((w for w in WEARS if f'({w})' in n), 'None')
    base = re.sub(r'^(★\s*)?(StatTrak™\s*)?(Souvenir\s*)?', '', n)
    base = re.sub(r'\s*\((' + '|'.join(WEARS) + r')\)$', '', base)
    weapon, _, skin = base.partition(' | ')
    if star and ('Gloves' in weapon or 'Wraps' in weapon): cat = 'Gloves'
    elif star: cat = 'Knife'
    elif weapon in W2C: cat = W2C[weapon]
    elif weapon == 'Sticker': cat = 'Sticker'
    elif 'Case' in name or 'Capsule' in name or 'Package' in name: cat = 'Container'
    else: cat = 'Other'
    return weapon, skin or '(vanilla)', wear, stattrak, souvenir, cat

items = pd.DataFrame({'item': sorted(d['item'].unique())})
items[['weapon','skin','wear','stattrak','souvenir','category']] = items['item'].apply(lambda s: pd.Series(parse(s)))
items.insert(0, 'item_id', range(1, len(items) + 1))
d = d.merge(items[['item_id','item']], on='item')

# ---- data-quality flags (kept in the fact table, shown on a DQ page) ------
d['dq_missing_buff'] = d['buff_price'].isna()
d['dq_missing_float'] = d['csfloat_price'].isna()
d['dq_extreme_markup'] = (d['markup_pct'] > 100) | (d['markup_pct'] < -50)
d['dq_extreme_buff_ratio'] = d['buff_pct'] > 1000
d['dq_any_issue'] = d[['dq_missing_buff','dq_missing_float','dq_extreme_markup','dq_extreme_buff_ratio']].any(axis=1)

# ---- index input: price relative to the item's May-2026 base median -------
base = d[(d['sale_ts'] < '2026-06-01') & ~d['dq_extreme_markup']].groupby('item_id')['price'].agg(['median','count'])
base = base[base['count'] >= 3]['median'].rename('base_price')
d = d.merge(base, on='item_id', how='left')
d['price_relative'] = d['price'] / d['base_price']
d['in_index'] = d['base_price'].notna() & ~d['dq_extreme_markup']

fact = d[['msg_id','sale_ts','sale_date','item_id','price','markup_pct','buff_price','buff_pct',
          'csfloat_price','float_pct','stickers_value','liquidity_pct','blacklisted',
          'base_price','price_relative','in_index',
          'dq_missing_buff','dq_missing_float','dq_extreme_markup','dq_extreme_buff_ratio','dq_any_issue']]
fact = fact.rename(columns={'msg_id': 'sale_id'})
fact['sale_ts'] = fact['sale_ts'].dt.strftime('%Y-%m-%d %H:%M:%S')

# ---- dim_date ----------------------------------------------------------------
dates = pd.DataFrame({'date': pd.date_range(d['sale_ts'].min().date(), d['sale_ts'].max().date())})
dates['year'] = dates.date.dt.year; dates['month'] = dates.date.dt.strftime('%Y-%m')
dates['iso_week'] = dates.date.dt.isocalendar().week.astype(int); dates['weekday'] = dates.date.dt.day_name()
dates['date'] = dates.date.dt.date

fact.to_csv('data/fact_sales.csv', index=False)
items.to_csv('data/dim_item.csv', index=False)
dates.to_csv('data/dim_date.csv', index=False)
print('fact_sales', fact.shape, '| dim_item', items.shape, '| dim_date', dates.shape)
print('in_index share', round(fact.in_index.mean() * 100, 1), '% | rows with a DQ issue', int(fact.dq_any_issue.sum()))
print(items.category.value_counts().to_string())
daily = d[d.in_index].groupby('sale_date')['price_relative'].median() * 100
print('index first/last week:', round(daily.head(7).mean(), 1), round(daily.tail(7).mean(), 1))
