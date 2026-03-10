# FedEx Backtest Checklist

**Purpose:** Ensure data quality and consistency before running predictive models or backtests.

---

## Pre-Processing Validation Gates

### 1. Schema Validation

**Check:** All required columns present and correct data types

- [ ] Weekly dataset has all Bronze key columns
- [ ] Aug dataset has all Bronze key columns (mapped)
- [ ] Numeric fields (PACKS, Shipments, aPounds) are numeric type
- [ ] Date fields (ship_date) are datetime type
- [ ] No unexpected column name changes

**Action if Failed:** STOP - verify source file integrity

---

### 2. Date Parsing Validation

**Check:** All dates parse correctly

- [ ] Weekly: shp_dt parses without errors
- [ ] Aug: ShipDate parses without errors
- [ ] No unparseable date strings (e.g., "00/00/0000")
- [ ] Date range is reasonable (2022-2024)

**Action if Failed:** Investigate unparseable rows, exclude or fix

---

### 3. Missingness Thresholds

**Check:** Key fields meet missingness requirements

Weekly Dataset:
- [ ] shp_dt: <1% missing
- [ ] ORIG_RAMP: <5% missing
- [ ] Product_Code: <5% missing
- [ ] PACKS: <1% missing
- [ ] Shipments: <1% missing
- [ ] aPounds: <1% missing

Aug Dataset:
- [ ] ShipDate: <1% missing
- [ ] ORIG_RAMP: <5% missing
- [ ] Product: <5% missing
- [ ] Packs: <1% missing
- [ ] Shipments: <1% missing
- [ ] aLbs: <1% missing
- [ ] Lane_: 20-40% missing (expected, recovery rule will address)

**Exception:** Customer fields in Aug dataset can be >50% missing (allowed)

**Action if Failed:** Document excess missingness, consider excluding affected date ranges

---

### 4. Lane Recovery Rule Application

**Check:** Lane_ nulls in Aug dataset addressed

- [ ] Recovery rule applied: IF Lane_ IS NULL AND Lane == "Americas" THEN Lane_ = "LA"
- [ ] Post-recovery Lane_ missingness reduced
- [ ] All recovered values properly mapped to Bronze Dest_Lane

**Action if Failed:** Re-apply recovery logic, check Lane field availability

---

### 5. Lane Harmonization

**Check:** Destination lanes standardized

- [ ] All "EU" values mapped to "Europe"
- [ ] All "AS" values mapped to "APAC"
- [ ] All "ME" values mapped to "MEISA"
- [ ] All "LA" values mapped to "Americas"
- [ ] No unmapped lane codes in Bronze Dest_Lane

**Action if Failed:** Review mapping rules, handle new lane codes

---

### 6. Non-Negativity Constraints

**Check:** Volume and weight fields are non-negative

- [ ] PACKS >= 0 (all records)
- [ ] Shipments >= 0 (all records)
- [ ] aPounds >= 0 (all records)
- [ ] No negative values detected

**Action if Failed:** Investigate negative values, exclude or correct (data quality issue)

---

### 7. Plausibility Checks

**Check:** Outliers identified but not removed

- [ ] lbs_per_pack calculated (aPounds / PACKS)
- [ ] Outliers by product identified using IQR method (3x threshold)
- [ ] Outlier list saved for review
- [ ] Outliers flagged, NOT automatically removed

**Action if Failed:** Review plausibility logic, document extreme values

---

### 8. Reconciliation Gates (Aug vs Weekly)

**Check:** Aug 2024 data reconciles with Weekly Aug 2024 data

Critical Reconciliation Checks:

- [ ] Aug dataset filtered to 2024-08-01 to 2024-08-31
- [ ] Weekly dataset filtered to 2024-08-01 to 2024-08-31
- [ ] Both aggregated to Bronze grain (ship_date, ramp, lane, product)
- [ ] PACKS delta calculated: abs(Aug - Weekly)
- [ ] Shipments delta calculated: abs(Aug - Weekly)
- [ ] aPounds delta calculated: abs(Aug - Weekly)

**Acceptable Thresholds:**

- Lane-level delta: <20% for PACKS, Shipments, aPounds
- Product-level delta: <30% for PACKS, Shipments, aPounds
- Ramp-level delta: <20% for PACKS, Shipments, aPounds

**Action if Failed:**
- If delta >50%: STOP - investigate aggregation logic differences
- If delta 20-50%: FLAG - document for business review
- If delta <20%: PASS - acceptable variance

---

### 9. Time Coverage Validation

**Check:** No unexpected gaps in time series

Weekly Dataset:
- [ ] Date range: 2022-01-01 to 2024-12-31 (approximately)
- [ ] No calendar week gaps >2 weeks
- [ ] All FY and WeekNbr combinations present

Aug Dataset:
- [ ] Date range: 2024-08-01 to 2024-08-31
- [ ] All dates in August 2024 represented

**Action if Failed:** Document gaps, create time continuity grid with zero-fill

---

### 10. Bronze Schema Compliance

**Check:** Output matches Bronze schema specification

- [ ] All Bronze keys present
- [ ] All Bronze measures present
- [ ] Data types match Bronze specification
- [ ] Grain is correct (daily or weekly by ramp/lane/product)

**Action if Failed:** Re-process data, check mapping logic

---

## Post-Processing Validation

### 11. Aggregation Validation

**Check:** Aggregated totals match source totals

- [ ] Total PACKS (Bronze) ~= Total PACKS (Weekly) + Total Packs (Aug)
- [ ] Total Shipments (Bronze) ~= Total Shipments (Weekly) + Total Shipments (Aug)
- [ ] Total aPounds (Bronze) ~= Total aPounds (Weekly) + Total aLbs (Aug)

**Tolerance:** <5% difference allowed due to exclusions/filters

**Action if Failed:** Investigate data loss during aggregation

---

### 12. Row Count Validation

**Check:** Expected row counts after processing

- [ ] Bronze row count is reasonable (not inflated, not too sparse)
- [ ] No duplicate keys in Bronze output
- [ ] GROUP BY keys are unique

**Action if Failed:** Check for duplicate rows, verify unique constraints

---

## Backtest-Ready Criteria

Before running any predictive model or backtest, ALL checks must PASS or be documented/approved:

**Bronze KPI Table Requirements:**
- [x] Schema validation: PASS
- [x] Date parsing: PASS
- [x] Missingness: PASS (with exceptions documented)
- [x] Lane recovery: APPLIED
- [x] Lane harmonization: APPLIED
- [x] Non-negativity: PASS
- [x] Plausibility: FLAGGED (outliers documented)
- [x] Reconciliation: DOCUMENTED (deltas reviewed)
- [x] Time coverage: VALIDATED
- [x] Bronze compliance: PASS

**Delay Modeling Requirements:**
- [ ] Promised delivery time: NOT AVAILABLE - BLOCKED
- [ ] Actual delivery time: NOT AVAILABLE - BLOCKED
- [ ] SLA labels: NOT AVAILABLE - BLOCKED
- [ ] Delay hours: NOT AVAILABLE - BLOCKED

---

## Automation

Run validation pipeline:
```bash
python src/quality/validation.py
```

Outputs generated:
- schema_type_checks.csv
- missingness_analysis.csv
- non_negativity_checks.csv
- plausibility_outliers.csv
- reconciliation_aug_vs_weekly.csv
- reconciliation_by_lane.csv
- reconciliation_by_product.csv
- reconciliation_by_ramp.csv

---

## Sign-Off

Before proceeding to modeling:

| Check | Status | Reviewer | Date |
|-------|--------|----------|------|
| All validation gates passed | | | |
| Reconciliation deltas acceptable | | | |
| Data blockers documented | | | |
| Bronze schema ready | | | |

**Notes:**
