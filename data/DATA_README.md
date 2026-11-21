# Manyavar data pack, Vibe Coders Hackathon Edition 3

Read this first. It takes three minutes and saves you an hour.

Manyavar (Vedant Fashions Limited) has set two problem statements. Both use the same data.

- A. Store Coach. Read `briefs/A_Store_Coach_brief.pdf`
- B. Stock Mover. Read `briefs/B_Stock_Mover_brief.pdf`

Your team builds on one of them, not both.

## What is in this pack

| Folder or file | What it is |
|---|---|
| `briefs/` | The two briefs from Manyavar. Each one ends with a guide to every column. |
| `csv/` | The data. 17 files. One file is one table. |
| `csv/data_dictionary.csv` | Every column explained, with an example. |
| `manyavar_data.xlsx` | The same 17 tables as tabs in one Excel file. Shared as a separate download. |

The CSV files and the Excel file hold the same data. Use whichever your tool likes. For code, use the CSVs.

## The data in one minute

20 Manyavar stores in six cities, and one warehouse (`WH-KOL`).
Sales run from 1 Nov 2024 to 31 Oct 2026. "Today" in this data is the close of 31 Oct 2026.
The data is synthetic. No real store, salesperson or customer is in it.

| File | One row is | Rows |
|---|---|---|
| stores | A store | 20 |
| area_managers | An area manager | 6 |
| items | A SKU, which is one style in one size | 385 |
| salespeople | A salesperson | 175 |
| roster_daily | A salesperson on a day, 1 May to 31 Oct 2026 | 23,569 |
| footfall_daily | A store on a day | 13,892 |
| bills | A bill | 90,805 |
| bill_lines | An item on a bill | 259,772 |
| stock_snapshot | A location and SKU, stock on 31 Oct 2026 | 3,547 |
| stock_weekly | A store, SKU and week, last 12 weeks | 61,416 |
| warehouse_inbound | A delivery due at the warehouse | 768 |
| calendar | A date in a state | 2,373 |
| rules | A stock rule | 8 |
| min_display | A tier and category | 24 |
| lead_times | A route | 6 |
| flagship_protected | A protected style at a flagship store | 80 |
| data_dictionary | A column | 36 |

## Which files you need

Store Coach: stores, area_managers, salespeople, roster_daily, footfall_daily, bills, bill_lines, items, calendar.

Stock Mover: stores, items, bills, bill_lines, stock_snapshot, stock_weekly, warehouse_inbound, calendar, rules, min_display, lead_times, flagship_protected.

Nothing stops you from using the rest.

## How the tables join

- `store_id` joins every table that has it to `stores`.
- `bill_id` joins `bill_lines` to `bills`.
- `sku_id` joins `bill_lines`, the stock tables and `warehouse_inbound` to `items`.
- `salesperson_id` joins `bills` and `roster_daily` to `salespeople`.
- `area_manager_id` joins `stores` to `area_managers`.
- `state` joins `stores` to `calendar`.
- `style_id` groups all the sizes of one design.

## Things people get wrong

1. Money is in rupees and includes GST.
2. Revenue for a line is `qty` times `selling_price`. A bill's value is the sum of its lines.
3. Discount per unit is `mrp` minus `selling_price`.
4. Packaging rows (`is_packaging` = 1) are carry bags and covers at Rs 0. They are not products. Leave them out when you count items per bill.
5. `customer_id` is a hashed mobile number. The same customer keeps the same ID across visits and stores.
6. In `stock_snapshot`, `location_id` is a store or the warehouse `WH-KOL`. The warehouse is not in `stores`.
7. The roster covers only 1 May to 31 Oct 2026. Sales go back two years.
8. Weeks in `stock_weekly` run Sunday to Saturday.
9. In `min_display`, one category is written "Accessories (Safa/Mala/Stole)". In `items`, Safa, Mala and Stole are three separate categories. Add them together.
10. In `lead_times`, the route is a sentence, not a code. Work out the route from each store's zone and city.
11. In `area_managers`, the `stores` column is a list in one cell, separated by commas.
12. Dates are written year, month, day, like 2026-10-31.
13. IDs are text. Do not let your tool turn them into numbers or dates.

## Blank cells

- `calendar.festival` is blank on a day with no festival.
- `stock_snapshot.in_transit_arrives_on` is blank when nothing is in transit.
- Any other blank is exactly as Manyavar sent it. Nothing in this data has been corrected or cleaned. Both briefs tell you how to treat data that does not look right.

## Loading it

- `bill_lines.csv` has about 2.6 lakh rows. Do not paste it into a chat window. Upload the file, or load it with code.
- If your AI tool takes a zip, give it the whole `csv` folder as one zip.
- In Python: `pandas.read_csv("csv/bills.csv", dtype=str)` and then convert the number columns you need.
- In Excel, open `manyavar_data.xlsx`. Do not open the CSVs by double click, because Excel may change the IDs.

## Questions

Ask your Manyavar contact in the room or any crew member with a black CREW card.

Data and briefs belong to Vedant Fashions Limited. Packed by Calcutta AI Club without changing any value.
