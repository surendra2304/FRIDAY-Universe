# Staged chart-analysis checklist — BTCUSDT

Generated: 2026-11-25T10:53:15.133286+00:00 (UTC) | Task: TASK-STR-086 | Worker: Muse TP6

Input: Data-rendered chart from real demo-fapi klines (venue: demo-fapi (Binance Demo Trading, public klines, no key)); symbol BTCUSDT; timeframes 1d, 4h, 1h, trading timeframe 1h. Not a broker-terminal screenshot.

**Verdict: BLOCKED**

## Per-stage summary

| Stage | Name | Status | Summary |
|---:|---|---|---|
| 1 | market_structure | ERROR | No klines: cannot assess structure. |
| 2 | data_quality | FAIL | Data quality FAIL (fail-closed): 1d: 250 bar(s) missing (0/250); 4h: 250 bar(s) missing (0/250); 1h: 250 bar(s) missing (0/250) |
| 3 | timeframe_context | BLOCKED | No timeframe regimes available. |
| 4 | fundamentals | PASS | No contradicting fundamental evidence in the available feed. On-chain/fundamental inputs are NOT AVAILABLE from a chart — the gap is named above, nothing is synthesised. |
| 5 | news_sentiment | INCONCLUSIVE | High-impact event(s) in window: CB Consumer Confidence, FGV Consumer confidence, Monthly CPI Indicator, Spanish PPI, Trimmed Mean CPI, Weighted mean CPI — no setup into the event without coordinator clearance. |
| 6 | risk_levels | BLOCKED | Data quality failed — risk levels are not computed on untrusted data. |
| 7 | final_report | BLOCKED | BLOCKED — the pipeline could not complete; see per-stage reasons. |

## Stage detail

### market_structure — ERROR

No klines: cannot assess structure.

```json
{
  "bars": 0
}
```

### data_quality — FAIL

Data quality FAIL (fail-closed): 1d: 250 bar(s) missing (0/250); 4h: 250 bar(s) missing (0/250); 1h: 250 bar(s) missing (0/250)

```json
{
  "venue": "demo-fapi (Binance Demo Trading, public klines, no key)",
  "per_timeframe": {
    "1d": {
      "expected_bars": 250,
      "received_bars": 0,
      "missing_bars": 250,
      "gaps": 0,
      "stale": null,
      "last_close_time": null
    },
    "4h": {
      "expected_bars": 250,
      "received_bars": 0,
      "missing_bars": 250,
      "gaps": 0,
      "stale": null,
      "last_close_time": null
    },
    "1h": {
      "expected_bars": 250,
      "received_bars": 0,
      "missing_bars": 250,
      "gaps": 0,
      "stale": null,
      "last_close_time": null
    }
  },
  "data_trusted": false,
  "problems": [
    "1d: 250 bar(s) missing (0/250)",
    "4h: 250 bar(s) missing (0/250)",
    "1h: 250 bar(s) missing (0/250)"
  ]
}
```

### timeframe_context — BLOCKED

No timeframe regimes available.

```json
{
  "regimes": {},
  "trading_timeframe": "1h",
  "agreement": false,
  "htf_conflict": false,
  "notes": []
}
```

### fundamentals — PASS

No contradicting fundamental evidence in the available feed. On-chain/fundamental inputs are NOT AVAILABLE from a chart — the gap is named above, nothing is synthesised.

```json
{
  "available_facts": {
    "symbol": "BTCUSDT",
    "venue": "demo-fapi (Binance Demo Trading, public klines, no key)",
    "contract_type": "USDT-M perpetual (Binance USD-margined futures)",
    "funding_rate": null,
    "funding_rate_source": null
  },
  "not_available_from_chart": [
    "on-chain flows",
    "exchange reserves / netflows",
    "open interest history",
    "liquidation map",
    "project/token fundamentals (revenue, unlocks, roadmap)",
    "order-book depth snapshot"
  ],
  "verdict": "NO_CONTRADICTING_EVIDENCE",
  "verdict_meaning": "PASS on this stage means 'no contradicting evidence found in the available feed', never 'fundamentals/news confirm'."
}
```

### news_sentiment — INCONCLUSIVE

High-impact event(s) in window: CB Consumer Confidence, FGV Consumer confidence, Monthly CPI Indicator, Spanish PPI, Trimmed Mean CPI, Weighted mean CPI — no setup into the event without coordinator clearance.

```json
{
  "window": "2026-11-25 to 2026-11-25",
  "events_in_window": [
    {
      "date": "2026-11-25",
      "time": "",
      "name": "5-Year Note Auction",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "4.708%",
      "forecast": " ",
      "actual": "4.719%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "52-Week Bill Auction",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "3.980%",
      "forecast": " ",
      "actual": "4.365%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "AACG earnings (ATA Creativity Global)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "AACG",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "ADP Employment Change Weekly",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "23.80K",
      "forecast": " ",
      "actual": "21.00K"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "ADXN earnings (Addex Therapeutics Ltd)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "ADXN",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "AEXA earnings (American Exceptionalism Acquisition Corp. A)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "AEXA",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "ALAR earnings (Alarum Technologies Ltd.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "ALAR",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "AMBR earnings (Amber International Holding Limited)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "AMBR",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "API Weekly Crude Oil Stock",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "5.300M",
      "forecast": "0.900M",
      "actual": "0.126M"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "BMA earnings (Macro Bank Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "BMA",
      "previous": "",
      "forecast": "$1.44",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "BRLS earnings (Borealis Foods Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "BRLS",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "BRTX earnings (BioRestorative Therapies, Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "BRTX",
      "previous": "",
      "forecast": "($2.60)",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "BZ earnings (KANZHUN LIMITED)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "BZ",
      "previous": "",
      "forecast": "($0.02)",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "BoC Gov Macklem Speaks",
      "kind": "macro",
      "impact": "low",
      "country": "Canada",
      "symbol": "",
      "previous": "&nbsp;",
      "forecast": " ",
      "actual": "&nbsp;"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "CAAS earnings (China Automotive Systems, Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "CAAS",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "CB Consumer Confidence",
      "kind": "macro",
      "impact": "high",
      "country": "United States",
      "symbol": "",
      "previous": "91.9",
      "forecast": "92.4",
      "actual": "103.3"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "CBI Distributive Trades Survey",
      "kind": "macro",
      "impact": "low",
      "country": "United Kingdom",
      "symbol": "",
      "previous": "-10",
      "forecast": "-27",
      "actual": "9"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "CETY earnings (Clean Energy Technologies, Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "CETY",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "CMCM earnings (Cheetah Mobile Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "CMCM",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Car Registration",
      "kind": "macro",
      "impact": "low",
      "country": "United Kingdom",
      "symbol": "",
      "previous": "12.0%",
      "forecast": " ",
      "actual": "5.4%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Construction Work Done",
      "kind": "macro",
      "impact": "low",
      "country": "Australia",
      "symbol": "",
      "previous": "-0.1%",
      "forecast": "0.8%",
      "actual": "0.9%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Corporate Services Price Index (CSPI)",
      "kind": "macro",
      "impact": "low",
      "country": "Japan",
      "symbol": "",
      "previous": "3.8%",
      "forecast": "3.6%",
      "actual": "4.2%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "DE earnings (Deere & Company)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "DE",
      "previous": "",
      "forecast": "$4.07",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "DSC earnings (DSC Holdings Ltd.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "DSC",
      "previous": "",
      "forecast": "($0.11)",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "DSX earnings (Diana Shipping inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "DSX",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "EDVA earnings (Endovia Health Sciences, Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "EDVA",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "EH earnings (EHang Holdings Limited)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "EH",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "EOCN earnings (Eocene Ltd.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "EOCN",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "FGV Consumer confidence",
      "kind": "macro",
      "impact": "high",
      "country": "Brazil",
      "symbol": "",
      "previous": "84.7",
      "forecast": " ",
      "actual": "83.5"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "FINV earnings (FinVolution Group)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "FINV",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Federal Tax Revenue",
      "kind": "macro",
      "impact": "low",
      "country": "Brazil",
      "symbol": "",
      "previous": "239.38B",
      "forecast": " ",
      "actual": "293.98B"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "French Car Registration",
      "kind": "macro",
      "impact": "low",
      "country": "France",
      "symbol": "",
      "previous": "11.6%",
      "forecast": " ",
      "actual": "7.0%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "GASS earnings (StealthGas, Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "GASS",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "GDS earnings (GDS Holdings Limited)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "GDS",
      "previous": "",
      "forecast": "$1.31",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "GOTU earnings (Gaotu Techedu Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "GOTU",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "German Business Expectations",
      "kind": "macro",
      "impact": "low",
      "country": "Germany",
      "symbol": "",
      "previous": "91.5",
      "forecast": "92.0",
      "actual": "91.9"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "German Car Registration",
      "kind": "macro",
      "impact": "low",
      "country": "Germany",
      "symbol": "",
      "previous": "20.8%",
      "forecast": " ",
      "actual": "-0.9%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "German Current Assessment",
      "kind": "macro",
      "impact": "low",
      "country": "Germany",
      "symbol": "",
      "previous": "88.8",
      "forecast": "89.2",
      "actual": "89.4"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "German Ifo Business Climate Index",
      "kind": "macro",
      "impact": "low",
      "country": "Germany",
      "symbol": "",
      "previous": "90.1",
      "forecast": "90.5",
      "actual": "90.6"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "HDL earnings (SUPER HI INTERNATIONAL HOLDING LTD.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "HDL",
      "previous": "",
      "forecast": "$0.01",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "House Price Index",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "444.3",
      "forecast": " ",
      "actual": "444.4"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "IMKTA earnings (Ingles Markets, Incorporated)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "IMKTA",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "India - Guru Nanak Jayanti",
      "kind": "macro",
      "impact": "low",
      "country": "India",
      "symbol": "",
      "previous": " ",
      "forecast": " ",
      "actual": " "
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Italian Car Registration",
      "kind": "macro",
      "impact": "low",
      "country": "Italy",
      "symbol": "",
      "previous": "9.8%",
      "forecast": " ",
      "actual": "5.0%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "LEE earnings (Lee Enterprises, Incorporated)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "LEE",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "LEXX earnings (Lexaria Bioscience Corp.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "LEXX",
      "previous": "",
      "forecast": "($0.90)",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "LI earnings (Li Auto Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "LI",
      "previous": "",
      "forecast": "($0.08)",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "LITB earnings (LightInTheBox Holding Co., Ltd.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "LITB",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Leading Indicators",
      "kind": "macro",
      "impact": "low",
      "country": "South Africa",
      "symbol": "",
      "previous": "119.60%",
      "forecast": " ",
      "actual": "119.30%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "M2 Money Supply",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "23.41T",
      "forecast": " ",
      "actual": "23.53T"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Monthly CPI Indicator",
      "kind": "macro",
      "impact": "high",
      "country": "Australia",
      "symbol": "",
      "previous": "4.30%",
      "forecast": "4.70%",
      "actual": "4.90%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "NNOX earnings (NANO-X IMAGING LTD)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "NNOX",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "NWCL earnings (newcleo plc)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "NWCL",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "OMSE earnings (OMS Energy Technologies Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "OMSE",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "OPHI earnings (CollPlant Biotechnologies Ltd.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "OPHI",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "PLG earnings (Platinum Group Metals Ltd.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "PLG",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "PSNY earnings (Polestar Automotive Holding UK Limited)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "PSNY",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "REBN earnings (Reborn Coffee, Inc.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "REBN",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Redbook",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "9.5%",
      "forecast": " ",
      "actual": "11.3%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Richmond Manufacturing Index",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "-2",
      "forecast": "-2",
      "actual": "3"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Richmond Manufacturing Shipments",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "0",
      "forecast": " ",
      "actual": "2"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Richmond Services Index",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "2",
      "forecast": " ",
      "actual": "-7"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "S&P/CS HPI Composite - 20 n.s.a.",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "-0.4%",
      "forecast": " ",
      "actual": "-0.5%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "S&P/CS HPI Composite - 20 s.a.",
      "kind": "macro",
      "impact": "low",
      "country": "United States",
      "symbol": "",
      "previous": "0.2%",
      "forecast": " ",
      "actual": "0.1%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "SJ earnings (Scienjoy Holding Corporation)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "SJ",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "SRTM earnings (Stratum Holdings Corp.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "SRTM",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Spanish PPI",
      "kind": "macro",
      "impact": "high",
      "country": "Spain",
      "symbol": "",
      "previous": "18.3%",
      "forecast": " ",
      "actual": "19.9%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Trimmed Mean CPI",
      "kind": "macro",
      "impact": "high",
      "country": "Australia",
      "symbol": "",
      "previous": "3.6%",
      "forecast": "3.6%",
      "actual": "3.8%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "UCFI earnings (CN Healthy Food Tech Group Corp.)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "UCFI",
      "previous": "",
      "forecast": "",
      "actual": ""
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Weighted mean CPI",
      "kind": "macro",
      "impact": "high",
      "country": "Australia",
      "symbol": "",
      "previous": "3.4%",
      "forecast": " ",
      "actual": "3.4%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "YSG earnings (Yatsen Holding Limited)",
      "kind": "earnings",
      "impact": "medium",
      "country": "",
      "symbol": "YSG",
      "previous": "",
      "forecast": "",
      "actual": ""
    }
  ],
  "high_impact_in_window": [
    {
      "date": "2026-11-25",
      "time": "",
      "name": "CB Consumer Confidence",
      "kind": "macro",
      "impact": "high",
      "country": "United States",
      "symbol": "",
      "previous": "91.9",
      "forecast": "92.4",
      "actual": "103.3"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "FGV Consumer confidence",
      "kind": "macro",
      "impact": "high",
      "country": "Brazil",
      "symbol": "",
      "previous": "84.7",
      "forecast": " ",
      "actual": "83.5"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Monthly CPI Indicator",
      "kind": "macro",
      "impact": "high",
      "country": "Australia",
      "symbol": "",
      "previous": "4.30%",
      "forecast": "4.70%",
      "actual": "4.90%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Spanish PPI",
      "kind": "macro",
      "impact": "high",
      "country": "Spain",
      "symbol": "",
      "previous": "18.3%",
      "forecast": " ",
      "actual": "19.9%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Trimmed Mean CPI",
      "kind": "macro",
      "impact": "high",
      "country": "Australia",
      "symbol": "",
      "previous": "3.6%",
      "forecast": "3.6%",
      "actual": "3.8%"
    },
    {
      "date": "2026-11-25",
      "time": "",
      "name": "Weighted mean CPI",
      "kind": "macro",
      "impact": "high",
      "country": "Australia",
      "symbol": "",
      "previous": "3.4%",
      "forecast": " ",
      "actual": "3.4%"
    }
  ],
  "calendar_note": "calendar read from store (refreshed).",
  "verdict": "HIGH_IMPACT_EVENT_IN_WINDOW",
  "verdict_meaning": "PASS on this stage means 'no contradicting evidence found in the available feed', never 'fundamentals/news confirm'."
}
```

### risk_levels — BLOCKED

Data quality failed — risk levels are not computed on untrusted data.

```json
{
  "direction": "NO_SETUP",
  "data_trusted": false
}
```

### final_report — BLOCKED

BLOCKED — the pipeline could not complete; see per-stage reasons.

```json
{
  "symbol": "BTCUSDT",
  "input": "Data-rendered chart from real demo-fapi klines (venue: demo-fapi (Binance Demo Trading, public klines, no key)); symbol BTCUSDT; timeframes 1d, 4h, 1h, trading timeframe 1h. Not a broker-terminal screenshot.",
  "verdict": "BLOCKED",
  "entry": null,
  "stop": null,
  "target": null,
  "risk_reward": null,
  "direction": "NO_SETUP",
  "per_stage": {
    "market_structure": {
      "status": "ERROR",
      "summary": "No klines: cannot assess structure."
    },
    "data_quality": {
      "status": "FAIL",
      "summary": "Data quality FAIL (fail-closed): 1d: 250 bar(s) missing (0/250); 4h: 250 bar(s) missing (0/250); 1h: 250 bar(s) missing (0/250)"
    },
    "timeframe_context": {
      "status": "BLOCKED",
      "summary": "No timeframe regimes available."
    },
    "fundamentals": {
      "status": "PASS",
      "summary": "No contradicting fundamental evidence in the available feed. On-chain/fundamental inputs are NOT AVAILABLE from a chart \u2014 the gap is named above, nothing is synthesised."
    },
    "news_sentiment": {
      "status": "INCONCLUSIVE",
      "summary": "High-impact event(s) in window: CB Consumer Confidence, FGV Consumer confidence, Monthly CPI Indicator, Spanish PPI, Trimmed Mean CPI, Weighted mean CPI \u2014 no setup into the event without coordinator clearance."
    },
    "risk_levels": {
      "status": "BLOCKED",
      "summary": "Data quality failed \u2014 risk levels are not computed on untrusted data."
    }
  },
  "feed_limits": "Stages 4-5 are feed-limited by design: a chart carries no fundamentals feed and no news feed. PASS there means 'no contradicting evidence found in the available feed', never 'fundamentals confirm'."
}
```

## Fetch failure

[1d] demo-fapi klines fetch failed for BTCUSDT 1d: HTTP 451 {
  "code": 0,
  "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://www.binance.com/en/terms. Please contact customer service if you believe you received this message in error."
}; [4h] demo-fapi klines fetch failed for BTCUSDT 4h: HTTP 451 {
  "code": 0,
  "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://www.binance.com/en/terms. Please contact customer service if you believe you received this message in error."
}; [1h] demo-fapi klines fetch failed for BTCUSDT 1h: HTTP 451 {
  "code": 0,
  "msg": "Service unavailable from a restricted location according to 'b. Eligibility' in https://www.binance.com/en/terms. Please contact customer service if you believe you received this message in error."
};

## Caveats

- Stages 4-5 are feed-limited by design; PASS there means 'no contradicting evidence found in the available feed'.
- The chart input is a data-rendered chart from real klines, not a screenshot of a broker terminal.
- Demo account only; no live trading; no orders placed.
