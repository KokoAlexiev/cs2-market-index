# CS2 market index (Power BI)

I wanted to see how the CS2 item market actually moved over the summer, so I built a price index
and a data quality report in Power BI on top of sales data I collected myself.

The data is 128,614 completed sales of 5,559 items on a CS2 item marketplace, from May to
September 2026.

## Where the data comes from

None of this comes from a ready-made dataset or a public API, I built the data collection myself.
My scrapers pick up every completed sale on the marketplace worth 40 coins or more (the
marketplace's own currency). That's the segment I care about: below 40 the handling per item isn't
worth it for logistical reasons, so I don't follow that part of the market. The reference prices are
scraped too: Buff prices with a headless browser, CSFloat prices with a regular (non-headless)
browser scraper. Every sale gets matched with those reference prices and stored as a row in a table.

The scrapers have been running 24/7 for over a year with very little downtime. To get there:

- every source (the marketplace, Buff and CSFloat) has more than one scraper running in parallel, so
  if one of them dies the others keep collecting while it gets revived, and no data is lost
- requests go through rotating proxies
- I found and fixed a memory leak in the browser scrapers, which lets them run for months without restarts
- I get an alert as soon as a source stops delivering data reliably

This report uses the May to September 2026 part of the data.

The export from that store is the input for `build_dataset.py`.

## What's in the report

The report has five pages.

### Price & Trend

The index over time with its 7 day average, and the same index split by category. Four cards at the
top show the current index, the change since May, the number of sales and their total value. You can
filter the whole page by category, date, wear and StatTrak.

![Price & Trend page](screenshots/1-price-and-trend.png)

### Distributions

How sales are spread across price, markup and liquidity, each as its own chart, plus the average
sale price by wear, kept in wear order (Factory New through Battle-Scarred) and not alphabetical.

![Distributions page](screenshots/2-distributions.png)

### Volume & Composition

The most sold items, the number of sales per category, where the money goes per category (a treemap
of total value), and the number of sales per weekday.

![Volume & Composition page](screenshots/3-volume-and-composition.png)

### Relationships & Reference

Average price against number of sales per category, average price against liquidity per weapon, how
sale prices compare to the Buff reference price per category, and StatTrak against non-StatTrak
prices.

![Relationships & Reference page](screenshots/4-relationships-and-reference.png)

### Data Quality

How many rows have a problem and what share that is, the issue rate per month, and a per item table
of sales and flagged rows.

![Data Quality page](screenshots/5-data-quality.png)

## How the index works

Every sale is compared to what that same item usually sold for in May. So if an AK sold for 90
and its May median was 100, that sale counts as 0.9. The index for a day is the median of all
those numbers times 100, so 100 means "May prices".

I used the median on purpose. Weird sales aren't rare in this market: a rare pattern, an extreme
float or expensive stickers can make one copy of a skin worth 10 or even 100 times its normal price
to the right collector. Those sales are real, not errors, but one of them would pull an average all
over the place. The median doesn't care, in either direction.

I also thought about cutting off everything above 3 standard deviations of the mean, but it doesn't
really work here: the same extreme sales inflate the mean and the standard deviation the cutoff is
based on, so a lot of them would survive it. If I wanted a cutoff I'd use one based on the median
absolute deviation instead. For a "what does a typical sale cost" index, the median is enough.

Items with fewer than 3 sales in May are left out of the index because there's no reliable base
price for them. Every item counts the same in the index, so it shows how the typical item's price
moved, not how the total value of the market moved.

About 91.5% of all sales end up in the index. The rest are items without enough May sales, or
sales with an extreme markup.

The index is built from completed sales only, so it shows what people actually paid, not what
sellers were asking. The price also includes the seller's markup on top of the reference price.
Every day's median comes from whatever happened to sell that day, so quiet days are noisier. That's
why the report shows a 7 day average and the number of sales next to the index. Prices are in the
marketplace's coins, not dollars, and days are in UTC.

By late September the index sits around 85, so the market is roughly 15% below where it was in May.

## Limitations

The 40 coin floor makes sense for what I'm looking at, but it does bias the index when the market
falls. When an item drops below 40 its sales stop showing up in the data, so the items that fell
the most leave the index exactly when prices go down. The real drop for the whole market is
probably a bit bigger than 15%. For the segment above 40 the number holds.

## Data quality checks

Real sales data is messy, so every row gets flagged if:

- the reference price from Buff is missing
- the CSFloat price is missing
- the markup is extreme (above 100% or below -50%)
- the price is more than 10x the Buff price

1,501 sales have at least one flag. They stay in the data and get reported on their own page, but
extreme markups are kept out of the index.

## Lakehouse version (Databricks)

I also loaded the same raw sales into Databricks (Free Edition) to try the bronze and silver setup.
The raw export goes in as `bronze_sales`, exactly as collected. A PySpark notebook
(`databricks/bronze_to_silver.ipynb`) turns it into `silver_sales`: proper types, wear and StatTrak
pulled out of the item name, a data quality flag on every row instead of dropping anything, and
duplicates removed. Out of 128,614 rows only one was a duplicate, so the collection itself is clean.

![Catalog with both tables](databricks/catalog.png)

![silver_sales columns and types](databricks/silver_schema.png)

## What I'd do next

- a value-weighted version, so it shows how the total value of the market moved and not only the
  typical item
- the same index built on Buff reference prices instead of sale prices, as a check that the trend
  isn't just sellers changing their markups

## Data model

Simple star schema:

- `fact_sales` - one row per sale (price, markup, reference prices, liquidity, index fields, quality flags)
- `dim_item` - item name split into weapon, skin, wear, StatTrak, souvenir and category
- `dim_date` - calendar table

`build_dataset.py` turns the raw sales export into these three tables. The raw data isn't in this
repo.

## Files

- `CS2_Market_Index.pbip`, with the `CS2_Market_Index.Report` and `CS2_Market_Index.SemanticModel`
  folders next to it - the Power BI project (report plus semantic model)
- `build_dataset.py` - the data prep (Python, pandas)
- `screenshots/` - one image per page
- `databricks/bronze_to_silver.ipynb` - the bronze to silver notebook (PySpark), with the catalog
  and schema screenshots in the same folder
