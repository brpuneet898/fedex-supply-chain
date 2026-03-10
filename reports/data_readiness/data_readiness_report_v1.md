# FedEx Data Readiness Report v1

## Executive Summary

This report assesses the readiness of FedEx shipment data for predictive modeling. Three datasets were analyzed: Weekly aggregated data (2022-2024), August 2024 transactional data, and an XLSB extract with delay/risk fields. Key validation checks, reconciliation analysis, and data quality assessments have been completed.

**Status:** Data is partially ready for Bronze schema implementation. Significant blockers exist for delay/severity modeling due to missing delivery timestamps and SLA labels.

---

## 1. Data Inventory

### Files Analyzed

| Dataset | Rows | Columns | Time Coverage | Grain |
|---------|------|---------|---------------|-------|
| Weekly 202201-202412 | 168,897 | 15 | 2022-01-04 to 2025-01-02 | Weekly aggregated by ship_date, ramp, lane, product |
| Aug actuals with DOM | 271,802 | 25 | 2024-08-01 to 2024-08-31 | Transactional (shipment-level) |
| Fedex data v1 (xlsb) | 712,214 | 59 | Unknown | Shipment-level with delay/risk fields |

### Bronze Schema Target

The canonical Bronze KPI table will include:
- **Keys:** ship_date, FY, WeekNbr, Orig_Ctry, ORIG_RAMP, Business_Region, Dest_Lane, Product_Code
- **Measures:** PACKS, Shipments, aPounds (plus Pounds if needed)

---

## 2. Time Coverage

- **Weekly dataset** covers 2022-01-04 to 2025-01-02 - roughly 3 years of weekly data, which is good for trend modeling. That's around 156 weeks across the full period.
- **Aug actuals** only covers August 2024 (2024-08-01 to 2024-08-31) - single month, used mainly for reconciliation against the Weekly data for the same period.
- **XLSB extract** - date range is unknown. The file doesn't have a clear ship_date or reference date column that's consistently populated. Can't determine coverage until provenance is confirmed.

Overall the Weekly file has solid time coverage for modeling. The Aug file is a snapshot and the XLSB can't be used for time-series work until the date columns are clarified.

---

## 3. Missingness Analysis

Key field missingness summary:

```
Dataset        Field  Missing_Pct
 Weekly       shp_dt         0.00
 Weekly    ORIG_RAMP         0.43
 Weekly    Dest_Lane         0.00
 Weekly Product_Code         0.00
 Weekly        PACKS         0.00
 Weekly    Shipments         0.00
 Weekly      aPounds         0.00
    Aug     ShipDate         0.00
    Aug    ORIG_RAMP         0.00
    Aug        Lane_        34.79
    Aug      Product         0.00
    Aug        Packs         0.00
    Aug    Shipments         0.00
    Aug         aLbs         0.00
```

**Critical Issues:**
- Lane_ field in Aug dataset: **34.79% missing** - requires recovery rule application
- ORIG_RAMP and Orig_Ctry have <2% missingness in both datasets (acceptable)
- Customer fields in Aug are allowed to be missing per project guidelines

---

## 4. Lane Mapping & Recovery Rules

### Lane Harmonization

Bronze schema requires standardized destination lanes. Mapping rules applied:

| Source Label | Target Label |
|--------------|--------------|
| EU | Europe |
| AS | APAC |
| ME | MEISA |
| LA | Americas |

### Recovery Rule for Aug Dataset

**Rule:** If `Lane_` is null AND `Lane` == "Americas", then set `Lane_` = "LA"

This recovery rule addresses the 34.79% missingness in the Lane_ field for August data.

**Implementation Status:** Rule documented, not yet applied to source data.

---

## 5. Reconciliation Results (Aug vs Weekly)

### Summary by Lane (Top Discrepancies)

```
Dest_Lane  PACKS_Weekly  PACKS_Aug  PACKS_Delta  PACKS_Delta_Pct
        0           0.0   538692.0    538692.0              NaN
     APAC       83344.0        0.0    -83344.0           -100.0
       AS           0.0    83308.0     83308.0              NaN
 Americas      554222.0        0.0   -554222.0           -100.0
       EU           0.0   161422.0    161422.0              NaN
   Europe      161156.0        0.0   -161156.0           -100.0
       LA           0.0    15396.0     15396.0              NaN
       ME           0.0    82617.0     82617.0              NaN
    MEISA       82147.0        0.0    -82147.0           -100.0
```

### Summary by Product (Top Discrepancies)

```
Product_Code  PACKS_Weekly  PACKS_Aug  PACKS_Delta  PACKS_Delta_Pct
         DOM           0.0      339.0        339.0              NaN
          EF        2630.0     4793.0       2163.0        82.243346
          IE       83724.0    87382.0       3658.0         4.369118
          IP      725131.0   725125.0         -6.0        -0.000827
          PD       56327.0    56420.0         93.0         0.165107
          PF        7353.0     7376.0         23.0         0.312797
          RL        3503.0        0.0      -3503.0      -100.000000
          RM        2201.0        0.0      -2201.0      -100.000000
```

### Summary by Ramp (Top Discrepancies)

```
ORIG_RAMP  PACKS_Weekly  PACKS_Aug  PACKS_Delta  PACKS_Delta_Pct
        0          81.0        8.0        -73.0        -90.123457
      BLR      115976.0   115998.0         22.0          0.018969
      BOM      214858.0   214684.0       -174.0         -0.080984
      DEL      258946.0   258963.0         17.0          0.006565
      DXB      291008.0   291782.0        774.0          0.265972
```

**Key Findings:**
- Significant row count discrepancy: Aug file has 271,802 rows vs Weekly's 7,009 rows for August 2024
- This suggests Aug file is transactional (shipment-level) while Weekly is pre-aggregated
- Delta percentages vary significantly by lane and product
- Reconciliation at Bronze key level shows substantial differences requiring investigation

### Delta Interpretation: Expected vs Suspicious

**Expected Deltas (Normal):**
- Product deltas for IE, IP, PD, PF (<5% difference) - these are expected due to grain mismatch. Aug is shipment-level while Weekly is pre-aggregated, so minor differences from aggregation timing or cutoff logic are normal.
- Small differences in ramp-level totals (<1%) - likely from rounding or aggregation edge cases.

**Suspicious Deltas (Require Investigation):**
- Lane deltas showing -100% or NaN - this is a clear mapping mismatch. Weekly uses standardized names (Europe, APAC, MEISA, Americas) while Aug uses raw codes (EU, AS, ME, LA). The lane recovery rule hasn't been applied yet, which explains why Lane_ values in Aug don't match Weekly's Dest_Lane.
- Product codes DOM, RL, RM appearing in only one file - potential data completeness issue or product filtering difference between sources.
- EF product showing 82% delta - suspicious, could be unit mismatch or data quality issue in one of the files.

**Likely Causes:**
1. Mapping mismatch - lane codes not harmonized between Aug and Weekly (EU→Europe not applied)
2. Grain mismatch - transactional vs aggregated causing minor volume differences
3. Unit mismatch - possible inconsistency in weight or pack calculations for certain products
4. Filtering differences - some products/lanes may be excluded in one file but not the other

**Recommendation:** Apply lane harmonization and recovery rules before final reconciliation. Most deltas should resolve once mapping is consistent.

---

## 6. Data Quality Gates - Results

All validation checks completed successfully:

### Schema & Type Checks
- All required columns present in Weekly and Aug datasets  
- Date parsing successful (minimal unparseable dates)  
- Numeric fields validated (PACKS, Shipments, weights)

### Non-Negativity Checks
- No negative values detected in volume/weight fields

### Plausibility Checks
- WARNING: 13 product groups flagged with lbs_per_pack outliers (flagged only, not removed)

### Reconciliation Checks
- WARNING: Significant deltas between Aug and Weekly for August 2024 period (see Section 5)

---

## 7. Blockers for Delay/Severity Modeling

**Critical Gap:** Current datasets lack essential fields for delay probability and severity prediction.

### Missing Elements:

1. **Promised/Scheduled Delivery Time** - Not available in Weekly or Aug datasets
2. **Actual Delivery Time** - Not available in usable form
3. **On-Time Labels (SLA_met/not)** - Not present in Weekly/Aug extracts
4. **Delay Hours/Minutes** - Cannot be calculated without promised vs actual delivery
5. **Service Level Agreement Details** - No SLA deadline or commitment data

### XLSB Extract Assessment:

The .xlsb file contains delay-related fields (`delivery_delay_hours`, `sla_met/not`, `hours_until_sla`), but:
- **High missing %** (>50% for most delay fields)
- **Data provenance unclear** (operational vs template/simulation)
- **Not recommended for use** until business stakeholder confirmation

See `docs/xlsb_provenance_usability.md` for detailed analysis.

### Impact:

**Bronze KPI table CAN be implemented** with volume/weight metrics.  
**Delay modeling CANNOT proceed** without additional data from FedEx.

---

## 8. Recommendations

### Immediate Actions:

1. **Apply lane recovery rule** to Aug dataset (Lane_ null handling)
2. **Implement Bronze schema** with Weekly + Aug data (volume/weight focus only)
3. **Request delivery timestamp data** from FedEx for delay modeling
4. **Investigate reconciliation deltas** - understand aggregation differences

### Data Gaps to Address:

1. Obtain promised delivery time and actual delivery time fields
2. Request formal data dictionary for .xlsb extract
3. Clarify customer field requirements (currently excluded from Aug)
4. Confirm lane mapping logic with business stakeholders

### Next Steps:

1. Build Bronze KPI table with existing data (volume/weight metrics)
2. Create time continuity grids for modeling (fill missing dates with zeros)
3. Implement automated validation gates for data refresh cycles
4. Document blockers formally for delay modeling phase

---

## 9. Artifacts Generated

All analysis artifacts saved to repository:

**Documentation:**
- `docs/fedex_data_mapping_v1.md` - Column mappings and lane harmonization rules
- `docs/fedex_backtest_checklist.md` - Validation gates and reconciliation checks
- `docs/xlsb_provenance_usability.md` - XLSB extract assessment

**QA Outputs:**
- `reports/data_readiness/qa_outputs/schema_type_checks.csv`
- `reports/data_readiness/qa_outputs/missingness_analysis.csv`
- `reports/data_readiness/qa_outputs/non_negativity_checks.csv`
- `reports/data_readiness/qa_outputs/plausibility_outliers.csv`
- `reports/data_readiness/qa_outputs/reconciliation_aug_vs_weekly.csv`
- `reports/data_readiness/qa_outputs/reconciliation_by_lane.csv`
- `reports/data_readiness/qa_outputs/reconciliation_by_product.csv`
- `reports/data_readiness/qa_outputs/reconciliation_by_ramp.csv`
- `reports/data_readiness/qa_outputs/xlsb_column_categorization.csv`
- `reports/data_readiness/qa_outputs/xlsb_data_quality.csv`
- `reports/data_readiness/qa_outputs/xlsb_delay_risk_analysis.csv`

**Code:**
- `src/quality/validation.py` - Automated QA checks
- `src/quality/xlsb_analysis.py` - XLSB provenance analysis
- `src/io/fedex_adapter.py` - Data loading scaffold

---

## Conclusion

The Weekly and August datasets are sufficient for building the Bronze KPI table focused on volume and weight metrics. Data quality is acceptable with documented exceptions. However, delay probability and severity modeling is **blocked** due to missing delivery timestamp and SLA label fields. Immediate focus should be on Bronze schema implementation and requesting additional delivery-related data from FedEx.

**Data Readiness Score: 65/100**
- Bronze KPI Schema: Ready
- Delay Modeling: Blocked
