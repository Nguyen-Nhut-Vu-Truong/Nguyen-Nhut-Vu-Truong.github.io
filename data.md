# Korean ETF Research Data — README

> **Last updated**: 2026-04-03
> **Project**: South Korean ETF Account-Level Trading Research
> **Data source**: Korea Exchange (KRX) via academic data access

---

## Overview

This folder contains datasets for studying account-level ETF trading behavior in the Korean market. Data spans **2006–2025** and includes intraday trade records, ETF characteristics, price data, constituent holdings, and stock characteristics.

**Important**: Raw intraday trading data (`.sas7bdat` files) are stored on **external disks** (E:/data/, D:/data/) due to their large size (~5 TB). Only processed/derived datasets are kept in this folder and on the C: drive.

---

## Data Dictionary

### 1. Variable description_Chinese Ver.xlsx (50 KB)

- **Description**: Metadata file documenting all variables in the raw intraday trading data (`.sas7bdat` files)
- **Language**: Chinese
- **Key variables documented**: `ENCRYP_ASK_ACNT_NO` / `ENCRYP_BID_ACNT_NO` (encrypted account IDs), `TRD_PRC` (trade price), `TRDVOL` (trade volume), `INVST_TP_CD` (investor type), `ORD_MEDIA_TP_CD` (order media: mobile/HTS/etc.), `ACNT_TP_CD` (account type), `PT_TP_CD` (program trading code), `REGUL_OFFHR_TP_CD` / `BRD_ID` (board/session filters), `SESS_ID` / `TRD_TP_CD` (session identifiers)
- **Note**: The raw data described here is NOT in this folder — it resides on external disks

---

### 2. allvar.sas7bdat (4.8 GB)

- **Description**: Stock-level daily characteristics for **all stocks** listed on the Korean Exchange
- **Format**: SAS dataset
- **Use case**: Cross-linking ETF traders with their stock trading activity — the same encrypted account ID (`ACNT_NO`) may appear in both ETF and stock trade records
- **Key for linking**: Account ID + date

---

### 3. kospi200_constituent_list(20040102~20220430).xlsx (18.5 MB)

- **Description**: Historical constituent list of the **KOSPI 200 Index**
- **Coverage**: 2004-01-02 to 2022-04-30
- **Use case**: Identifying which stocks are in the KOSPI 200 at any given date; useful for studying index-tracking ETFs (e.g., KODEX 200)

---

### 4. chk_ind.sas7bdat (896 KB)

- **Description**: Industry classification indicator for Korean listed stocks
- **Format**: SAS dataset
- **Key variable**: `financial` — equals **1** if the stock is a financial sector stock (金融股), 0 otherwise
- **Use case**: Filtering out financial stocks in analyses, sector-level subsample tests

---

### 5. Daily data on changes in ETF constituents/ (subfolder, ~8 GB)

- **Description**: Daily portfolio holdings (constituent stocks/assets) for Korean ETFs
- **Format**: 7 Excel files (`ETF_Portfolio.xlsx` through `ETF_Portfolio_7.xlsx`) + 1 zip archive
- **Language**: Korean column headers
- **Key columns**:
  - `날짜` (date)
  - `ETF코드` (ETF code)
  - `ETF명` (ETF name)
  - `구성종목코드` (constituent stock code)
  - `구성종목` (constituent name)
  - `주식수(계약수)` (number of shares/contracts)
  - `금액` (amount in KRW)
  - `금액기준 구성비중(%)` (weight %)
- **Use case**: Tracking how ETF portfolios change over time; studying creation/redemption activity; identifying which stocks are held by specific ETFs

---

### 6. ETF_Data_combined.csv (65 MB) — Processed from ETF_Data.xlsx

- **Description**: ETF-level daily market characteristics in **long format** (one row per ETF-day)
- **Rows**: 1,540,861
- **Coverage**: 2006-01-02 to 2025-12-30
- **Unique ETFs**: 1,300
- **Columns**: `date`, `etf_code`, `close`, `volume`, `dollar_volume`, `return`, `nav`, `open`, `high`, `low`, `market_cap`, `shares_outstanding`
- **Source**: Processed from `ETF_Data.xlsx` (322 MB, wide-format DataGuide download with metadata header rows)
- **Note**: `ETF_Data.xlsx` is the raw DataGuide download (wide format, 종가/close prices, refresh date 2026-02-27); `ETF_Data_combined.csv` is the cleaned long-format version

---

### 7. ETF_Char.xlsx (163 KB)

- **Description**: Cross-sectional ETF characteristics (one row per ETF, time-invariant)
- **Rows**: 992 unique ETFs
- **Key columns**:
  - `isu_cd` — ISIN code
  - `cd` — Short ETF code (6-digit) — **primary key for linking**
  - `Kr_Name` / `Eng_Name` — ETF name in Korean / English
  - `listing_name` — Listing date
  - `underlying index` — Benchmark index name
  - `tracking_multiple` — General (902), 2X_Lev (45), 1X_inverse (35), 2X_inverse (8), 1.5X_Lev (2)
  - `복제방법` — Replication method: Physical_Passive, Physical_Active, Synthetic
  - `underlying_mkt` — Domestic (537), Oversea (406), Domestic&Oversea (49)
  - `underlying_type` — Stock (708), Bond (155), Mixed (56), Commodity (23), Other (27), ForeignCurrency (12), RealEstate (11)
  - `fund_mgt_company` — Fund management company
  - `total_compensation` — Total expense ratio (%)
  - `tax_type` — Tax treatment

---

### 8. Data_ETF_price_combined.rds (12 MB)

- **Description**: ETF daily close prices in **long format** (one row per ETF-day)
- **Rows**: 6,044,709
- **Coverage**: 2006-01-02 to 2025-09-15
- **Columns**: `date` (numeric YYYYMMDD), `cd` (6-digit ETF code), `close_price`, `adjusted_close_price`
- **Format**: R `.rds` file
- **Source**: Reshaped from `Data_ETF_close_price.xlsx` (76 MB, wide format with 1,244 ETFs as columns)
- **Use case**: Joined to intraday trade data in V3 processing script to compute buy/sell returns relative to daily close price
- **Also located at**: `C:/Users/user/Desktop/PhD Courses/08_Short Selling ETFs/Data_ETF_price_combined.rds`

---

### 9. Account-ETF-Day Trading Data (Processed Output)

- **Location (V3 output)**: `C:/Users/user/Documents/data/ETF trading/process4/combined/`
- **Location (V1/V2 output)**: `C:/Users/user/Documents/data/ETF trading/process/combined/`
- **Description**: Aggregated investor-ETF-day level trading records processed from raw intraday `.sas7bdat` files
- **Total files**: 9 chunks per folder
- **Total size**: ~9.8 GB per folder
- **Chunk ranges**: 1–1000, 1001–1500, 1501–2000, 2001–2500, 2501–3000, 3001–3500, 3501–4000, 4001–4447, 4448–4691
- **Columns**:
  - `date` — Trading date
  - `ACNT_NO` — Encrypted account ID
  - `cd` — ETF code
  - `inv_type` — 1 = Domestic Individual, 2 = Domestic Institutional, 3 = Foreign
  - `b_vol` / `s_vol` — Total buy/sell volume (shares)
  - `b_val` / `s_val` — Total buy/sell value (KRW)
  - `b_ret` — Buy return: `mean(log(close_price / buy_price))`
  - `s_ret` — Sell return: `mean(-log(close_price / sell_price))` = `mean(log(sell_price / close_price))`
  - `b_n_trans` / `s_n_trans` — Number of buy/sell transactions
  - `spread_step1` — Bid-ask spread (best quote)
  - `spread_hl` — High-low spread

**Difference between process/ and process4/**:
- `process/` (V1/V2): Close price computed **from trade data** (`max(CLSPRC)` at session 30)
- `process4/` (V3): Close price from **external price file** (`Data_ETF_price_combined.rds`) — more reliable

---

## Other Files in This Folder

| File | Size | Description |
|---|---|---|
| `Data_ETF_close_price.xlsx` | 76 MB | Wide-format daily close prices (1,244 ETF columns × trading days), source for `Data_ETF_price_combined.rds` |
| `Data_ETF_ver0.xlsx` | 103 MB | Earlier version of ETF data download (refresh date: 2025-09-15) |
| `ETF_Data.xlsx` | 307 MB | Raw DataGuide download (wide format with metadata headers), source for `ETF_Data_combined.csv` |

---

## Raw Data Location (External Disks)

The raw intraday trading data consists of **4,691 SAS files** (`etf_trade1.sas7bdat` through `etf_trade4691.sas7bdat`):

| File Range | Disk | Schema |
|---|---|---|
| 1–4300 | E:/data/ | Files 1–795: `REGUL_OFFHR_TP_CD` + `TRD_TP_CD`; Files 796–4300: `BRD_ID` + `SESS_ID` |
| 4301–4450 | D:/data/ | `BRD_ID` + `SESS_ID` |
| 4451–4691 | E:/data/ | `BRD_ID` + `SESS_ID` |

---

## Processing Scripts

Located at: `C:/Users/user/Documents/data/ETF trading/`

| Script | Description |
|---|---|
| `ETF_trading.R` (V1) | Original version — kept as archive, **do not use for new processing** |
| `ETF_trading_2.R` (V2) | Clean self-contained script; computes close price from trade data; outputs to `process/` |
| `ETF_trading_3.R` (V3) | **Definitive version**; uses external price file; outputs to `process4/`; includes QA comparison function |

---

## Key Linking Variables

| Link | Key |
|---|---|
| Trade data ↔ ETF characteristics | `cd` (6-digit ETF code) |
| Trade data ↔ Price data | `cd` + `date` (TRD_DD) |
| ETF traders ↔ Stock trades | `ACNT_NO` (encrypted account ID) |
| ETF ↔ KOSPI 200 membership | `cd` + date |

