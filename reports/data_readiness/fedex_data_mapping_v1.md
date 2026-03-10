
# FedEx Data Mapping – Canonical Bronze Schema (v1)

## 1. Purpose

This document defines the **Canonical Bronze KPI schema**, data harmonization rules, unit standards, and lane mapping logic applied while consolidating multiple FedEx source datasets.

This mapping ensures:

* Schema consistency across sources
* Harmonized categorical dimensions
* Standardized weight units
* Deterministic transformation rules
* Reproducible data engineering process

---

# 2. Source Systems

The Bronze dataset is built from the following inputs:

## 2.1 Weekly KPI Dataset (2022–2024)

Aggregated weekly metrics including:

* Orig_Ctry
* ORIG_RAMP
* Business_Region
* Dest_Lane
* FY
* Product_Code
* PACKS
* Shipments
* aPounds

---

## 2.2 August Actuals with DOM

Shipment-level weekly aggregates including:

* Direction
* ShipDate
* ORIG_RAMP
* Orig_Ctry
* Business_Region
* Lane_ (short code)
* Lane (long name)
* Product
* Prod_Type
* yyyymm
* WeekNbr
* Packs
* aLbs
* Shipments

---

# 3. Canonical Bronze Schema

## 3.1 Primary Keys

The Bronze dataset is defined at the following grain:

```
FY
WeekNbr
Orig_Ctry
ORIG_RAMP
Business_Region
Dest_Lane
Product_Code
```

Each row represents:

> One product movement per origin ramp per destination lane per fiscal week.

---

## 3.2 Measures

| Field     | Description                | Unit   |
| --------- | -------------------------- | ------ |
| PACKS     | Total packages shipped     | Count  |
| Shipments | Total shipment records     | Count  |
| aPounds   | Total actual billed weight | Pounds |

---

## 3.3 Derived Fields (Where Applicable)

| Field     | Description                      |
| --------- | -------------------------------- |
| ship_date | Representative shipment date     |
| yyyymm    | Year-Month derived from ShipDate |

---

# 4. Lane Harmonization Rules

Different datasets used inconsistent lane representations.

## 4.1 Standardized Destination Lane Mapping

| Short Code (Lane_) | Long Name (Lane) | Canonical Dest_Lane |
| ------------------ | ---------------- | ------------------- |
| EU                 | Europe           | Europe              |
| AS                 | APAC             | APAC                |
| ME                 | MEISA            | MEISA               |
| NA                 | Americas         | Americas            |
| LA                 | Americas         | Americas            |

Final Bronze field:

```
Dest_Lane
```

All lane values are standardized to unified business lane names.

---

## 4.2 August Lane_ Recovery Rule

In the August dataset, some records contain:

* `Lane_` = NULL
* `Lane` = "Americas"

Recovery rule applied:

```
IF Lane_ IS NULL AND Lane = "Americas"
THEN Lane_ = "LA"
```

This ensures consistency between short-code and long-name representations.

This rule is deterministic and applied before harmonization.

---

# 5. Column Standardization

## 5.1 Weight Normalization

Source weight fields:

* aLbs
* aPounds
* kg (where present)

Canonical unit:

```
aPounds
```

Transformations:

* All weight fields converted to numeric
* aLbs renamed to aPounds
* kg converted to pounds when necessary
* Negative values flagged in QA

---

## 5.2 Measure Alignment

| Source Field | Canonical Field |
| ------------ | --------------- |
| Packs        | PACKS           |
| PACKS        | PACKS           |
| Shipments    | Shipments       |
| aLbs         | aPounds         |
| aPounds      | aPounds         |

All datasets are aligned before concatenation.

---

# 6. Bronze Consolidation Logic

Steps applied:

1. Rename columns to canonical names
2. Apply lane mapping harmonization
3. Apply August Lane_ recovery rule
4. Standardize weight units
5. Align schema across datasets
6. Concatenate sources
7. Fill missing numeric measures with 0
8. Enforce primary key structure

Result:

```
bronze_kpi_weekly_final
```

---

# 7. Time Continuity Enforcement

To support time-series modeling and prevent sparse bias:

A full weekly grid is generated across:

```
ORIG_RAMP × Dest_Lane × Product_Code × FY × WeekNbr
```

Missing combinations are filled with:

```
PACKS = 0
Shipments = 0
aPounds = 0
```

This ensures:

* No missing weeks
* Modeling-ready continuity
* Deterministic KPI aggregation

---

# 8. Data Quality Controls (Linked to validation module)

The Bronze dataset is validated for:

* Missingness summary
* Non-negativity checks
* Extreme value plausibility flags
* Schema consistency

Outputs are stored under:

```
reports/data_readiness/qa_outputs/
```

---
