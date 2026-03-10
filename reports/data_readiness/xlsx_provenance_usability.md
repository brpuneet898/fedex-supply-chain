# FedEx .xlsb Extract - Provenance & Usability Assessment

**File:** `Fedex data version 1 (1).xlsb`  
**Analysis Date:** 2026-02-19  
**Total Rows:** 712,214  
**Total Columns:** 59

---

## 1. Column Classification

### Operational Columns (13)
Columns that appear to contain real operational/transactional data:

- shipment_id
- shipment_date
- origin_hub/Loc
- destination_hub/Loc
- customer_id
- product_type
- service_name
- actual_weight_kg
- length_cm
- width_cm
- height_cm
- package_type
- actual_delivery_time

### Engineered/Template Columns (22)
Columns that appear to be calculated, derived, or template fields:

- total_containers_today
- containers_already_booked
- purple_tail_allocated_containers
- purple_tail_current_bookings
- commercial_allocated_containers
- commercial_current_bookings
- ip_ipf_reserved_containers
- hours_until_sla
- total_sla_hours
- delay_tolerance_days
- customer_tier_multiplier
- base_fuel_cost_per_km
- fuel_cost_total
- handling_cost_purple
- handling_cost_commercial
- route_efficiency_score
- container_total_weight
- container_total_volume
- consolidation_efficiency
- carbon_emissions_kg
- ... and 2 more

---

## 2. Data Quality Concerns

### High Missing Data (>50%)
The following columns have more than 50% missing values:

- customer_selected_priority
- service_revenue
- actual_weight_kg
- length_cm
- width_cm
- height_cm
- volumetric_weight_kg
- billable_weight_kg
- package_type
- flights_scheduled_today
- total_containers_today
- containers_already_booked
- next_flight_departure_time
- next_flight_available_containers
- booking_cutoff_time
- purple_tail_allocated_containers
- purple_tail_current_bookings
- commercial_allocated_containers
- commercial_current_bookings
- ip_ipf_reserved_containers
- ... and 29 more

### Constant/Invariant Columns (>90%)
The following columns have >90% constant values (low variance):

- shipment_date
- origin_hub/Loc
- destination_hub/Loc
- customer_id
- product_type
- service_name
- sla_deadline
- customer_tier
- sla_met/not

---

## 3. Delay/Risk Field Analysis

Key fields relevant to delay probability and severity modeling:

```
                     Field  Missing_Pct  Constant_Pct Usability
      delivery_delay_hours        100.0          0.00       Low
               sla_met/not          0.0         76.37      High
           hours_until_sla        100.0          0.00       Low
           total_sla_hours        100.0          0.00       Low
      delay_tolerance_days        100.0          0.00       Low
      hub_congestion_level        100.0          0.00       Low
            weather_impact        100.0          0.00       Low
      actual_delivery_time        100.0          0.00       Low
              sla_deadline          0.0          6.58      High
       booking_cutoff_time        100.0          0.00       Low
next_flight_departure_time        100.0          0.00       Low
```

### Critical Findings:
- **High Usability:** 2 fields
- **Medium Usability:** 0 fields
- **Low Usability:** 9 fields
- **Not Available:** 0 fields

---

## 4. Provenance Assessment

**Source Clarity:** Unknown - no metadata or documentation provided with file  
**Data Lineage:** Unclear if operational extract or simulation/template  
**Time Period:** Not explicitly labeled in file  
**Update Frequency:** Unknown

---

## 5. Recommendation

**USE WITH EXTREME CAUTION**

This .xlsb file should **NOT** be used for modeling or analysis until:

1. **Column definitions are confirmed** - Many fields appear engineered but lack documentation
2. **Data provenance is verified** - Source system and extraction date unknown
3. **Field validation is completed** - High missing % and constant values suggest incomplete/template data
4. **Business stakeholder sign-off** - Confirm which fields are authoritative

### Specific Blockers for Delay/Severity Modeling:
- Missing reliable actual vs. promised delivery timestamps
- `sla_met/not` and `delivery_delay_hours` require validation
- Many "delay/risk" fields have high missing % or constant values
- No clear linkage to Bronze schema (ship_date, ORIG_RAMP, Product_Code)

### Recommended Actions:
1. Request formal data dictionary for all 59 columns
2. Confirm if this is production data or simulation template
3. Verify if delay/risk fields are historical actuals or forecasts
4. Do NOT merge with Weekly/Aug datasets without confirmation

---

## 6. Detailed Artifacts

Full analysis outputs available in:
- `xlsb_column_categorization.csv` - Column classification
- `xlsb_data_quality.csv` - Missing % and constant % for all columns
- `xlsb_delay_risk_analysis.csv` - Focused analysis on delay/risk fields

---

**Conclusion:** This extract contains many fields that *appear* relevant to delay modeling, but data quality issues and lack of provenance make it unsuitable for immediate use. Treat as exploratory only until business confirmation is obtained.
