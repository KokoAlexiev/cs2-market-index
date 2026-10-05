# Databricks notebook source
# MAGIC %md
# MAGIC # Silver to gold (star schema)
# MAGIC
# MAGIC Builds the three tables the Power BI report reads: a sales fact plus an item and a
# MAGIC date dimension, including the price-index fields (each sale against its item's May
# MAGIC baseline). The report connects straight to these gold tables.

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, BooleanType
from pyspark.sql.window import Window
import re

bronze = spark.read.table("workspace.default.bronze_sales")

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
    stattrak = 'StatTrak' in n
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
    return (weapon, skin or '(vanilla)', wear, stattrak, souvenir, cat)

schema = StructType([
    StructField('weapon', StringType()), StructField('skin', StringType()),
    StructField('wear', StringType()), StructField('stattrak', BooleanType()),
    StructField('souvenir', BooleanType()), StructField('category', StringType()),
])
parse_udf = F.udf(parse, schema)

items = bronze.select('item').distinct()
items = items.withColumn('item_id', F.row_number().over(Window.orderBy('item')))
items = items.withColumn('p', parse_udf('item'))
dim_item = items.select('item_id','item',
    F.col('p.weapon').alias('weapon'), F.col('p.skin').alias('skin'),
    F.col('p.wear').alias('wear'), F.col('p.stattrak').alias('stattrak'),
    F.col('p.souvenir').alias('souvenir'), F.col('p.category').alias('category'))
print(dim_item.count())

# COMMAND ----------

d = bronze
d = d.withColumn('sale_ts_ts', F.to_timestamp('ts'))
d = d.withColumn('sale_date', F.to_date('sale_ts_ts'))
for c in ['price','markup_pct','buff_price','buff_pct','csfloat_price','float_pct','stickers_value','liquidity_pct']:
    d = d.withColumn(c, F.col(c).cast('double'))

d = d.join(dim_item.select('item_id','item'), on='item', how='inner')

d = d.withColumn('dq_missing_buff', F.col('buff_price').isNull())
d = d.withColumn('dq_missing_float', F.col('csfloat_price').isNull())
d = d.withColumn('dq_extreme_markup', (F.col('markup_pct') > 100) | (F.col('markup_pct') < -50))
d = d.withColumn('dq_extreme_buff_ratio', F.col('buff_pct') > 1000)
d = d.withColumn('dq_any_issue',
    F.col('dq_missing_buff') | F.col('dq_missing_float') | F.col('dq_extreme_markup') | F.col('dq_extreme_buff_ratio'))

# base price: each item's median price in May, items with at least 3 base-month sales,
# extreme markups left out of the baseline
base = (d.filter((F.col('sale_ts_ts') < '2026-06-01') & (~F.col('dq_extreme_markup')))
          .groupBy('item_id')
          .agg(F.expr('percentile(price, 0.5)').alias('median'), F.count('*').alias('cnt')))
base = base.filter(F.col('cnt') >= 3).select('item_id', F.col('median').alias('base_price'))

d = d.join(base, on='item_id', how='left')
d = d.withColumn('price_relative', F.col('price') / F.col('base_price'))
d = d.withColumn('in_index', F.col('base_price').isNotNull() & (~F.col('dq_extreme_markup')))

fact = d.select(
    F.monotonically_increasing_id().alias('sale_id'),
    F.date_format('sale_ts_ts','yyyy-MM-dd HH:mm:ss').alias('sale_ts'),
    'sale_date','item_id','price','markup_pct','buff_price','buff_pct',
    'csfloat_price','float_pct','stickers_value','liquidity_pct',
    F.lit(False).alias('blacklisted'),
    'base_price','price_relative','in_index',
    'dq_missing_buff','dq_missing_float','dq_extreme_markup','dq_extreme_buff_ratio','dq_any_issue')
print(fact.count(), round(fact.filter('in_index').count()/fact.count()*100,1))

# COMMAND ----------

b = d.select(F.min('sale_date').alias('mn'), F.max('sale_date').alias('mx')).first()
dim_date = spark.sql(f"SELECT explode(sequence(to_date('{b.mn}'), to_date('{b.mx}'), interval 1 day)) AS date")
dim_date = (dim_date
    .withColumn('year', F.year('date'))
    .withColumn('month', F.date_format('date','yyyy-MM'))
    .withColumn('iso_week', F.weekofyear('date'))
    .withColumn('weekday', F.date_format('date','EEEE')))

# COMMAND ----------

fact.write.mode('overwrite').option('overwriteSchema','true').saveAsTable('workspace.default.fact_sales')
dim_item.write.mode('overwrite').option('overwriteSchema','true').saveAsTable('workspace.default.dim_item')
dim_date.write.mode('overwrite').option('overwriteSchema','true').saveAsTable('workspace.default.dim_date')

display(spark.sql("""
  SELECT d.month, COUNT(*) sales, ROUND(percentile(f.price,0.5),2) median_price
  FROM workspace.default.fact_sales f JOIN workspace.default.dim_date d ON f.sale_date = d.date
  WHERE f.in_index GROUP BY d.month ORDER BY d.month
"""))
