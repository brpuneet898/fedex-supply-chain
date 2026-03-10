import pandas as pd
import numpy as np
from pathlib import Path


class XLSBAnalyzer:
    
    def __init__(self, xlsb_file, output_dir):
        self.xlsb_file = xlsb_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.operational_indicators = [
            'shipment_id', 'shipment_date', 'origin', 'destination', 'customer_id',
            'product_type', 'service_name', 'actual_weight', 'package_type',
            'actual_delivery', 'length_cm', 'width_cm', 'height_cm'
        ]
        
        self.engineered_indicators = [
            'hours_until', 'multiplier', 'efficiency', 'cost', 'emissions',
            'tolerance', 'factor', 'score', 'allocated', 'reserved', 
            'already_booked', 'current_bookings', 'total_'
        ]
        
        self.delay_risk_fields = [
            'delivery_delay_hours', 'sla_met/not', 'hours_until_sla', 
            'total_sla_hours', 'delay_tolerance_days', 'hub_congestion_level',
            'weather_impact', 'actual_delivery_time', 'sla_deadline',
            'booking_cutoff_time', 'next_flight_departure_time'
        ]
        
    def load_data(self):
        self.df = pd.read_excel(self.xlsb_file, engine='pyxlsb')
        
    def categorize_columns(self):
        categorization = []
        
        for col in self.df.columns:
            col_lower = col.lower()
            
            is_operational = any(indicator in col_lower for indicator in self.operational_indicators)
            is_engineered = any(indicator in col_lower for indicator in self.engineered_indicators)
            
            if is_operational and not is_engineered:
                category = 'Operational'
            elif is_engineered:
                category = 'Engineered/Template'
            else:
                category = 'Ambiguous'
            
            categorization.append({
                'Column': col,
                'Category': category,
                'Data_Type': str(self.df[col].dtype)
            })
        
        self.df_categorization = pd.DataFrame(categorization)
        self.df_categorization.to_csv(self.output_dir / 'xlsb_column_categorization.csv', index=False)
        
    def analyze_data_quality(self):
        
        quality_report = []
        
        for col in self.df.columns:
            total_rows = len(self.df)
            missing_count = self.df[col].isna().sum()
            missing_pct = (missing_count / total_rows) * 100
            
            non_missing = self.df[col].dropna()
            if len(non_missing) > 0:
                unique_count = non_missing.nunique()
                constant_pct = ((total_rows - missing_count - unique_count + 1) / (total_rows - missing_count)) * 100 if (total_rows - missing_count) > 0 else 0
                
                if unique_count == 1:
                    constant_pct = 100.0
            else:
                unique_count = 0
                constant_pct = 0.0
            
            is_delay_risk = col in self.delay_risk_fields
            
            quality_report.append({
                'Column': col,
                'Total_Rows': total_rows,
                'Missing_Count': missing_count,
                'Missing_Pct': round(missing_pct, 2),
                'Unique_Values': unique_count,
                'Constant_Pct': round(constant_pct, 2),
                'Delay_Risk_Field': 'Yes' if is_delay_risk else 'No'
            })
        
        self.df_quality = pd.DataFrame(quality_report)
        self.df_quality.to_csv(self.output_dir / 'xlsb_data_quality.csv', index=False)
        
    def analyze_delay_risk_fields(self):
        
        delay_risk_analysis = []
        
        for col in self.delay_risk_fields:
            if col in self.df.columns:
                total_rows = len(self.df)
                missing_count = self.df[col].isna().sum()
                missing_pct = (missing_count / total_rows) * 100
                
                non_missing = self.df[col].dropna()
                if len(non_missing) > 0:
                    unique_count = non_missing.nunique()
                    
                    if unique_count == 1:
                        constant_pct = 100.0
                        constant_value = non_missing.iloc[0]
                    else:
                        value_counts = non_missing.value_counts()
                        most_common_count = value_counts.iloc[0]
                        constant_pct = (most_common_count / len(non_missing)) * 100
                        constant_value = value_counts.index[0]
                else:
                    unique_count = 0
                    constant_pct = 0.0
                    constant_value = None
                
                usability = 'High' if missing_pct < 10 and constant_pct < 90 else 'Medium' if missing_pct < 50 else 'Low'
                
                delay_risk_analysis.append({
                    'Field': col,
                    'Missing_Pct': round(missing_pct, 2),
                    'Constant_Pct': round(constant_pct, 2),
                    'Unique_Values': unique_count,
                    'Most_Common_Value': str(constant_value)[:50] if constant_value is not None else 'N/A',
                    'Usability': usability
                })
            else:
                delay_risk_analysis.append({
                    'Field': col,
                    'Missing_Pct': 100.0,
                    'Constant_Pct': 0.0,
                    'Unique_Values': 0,
                    'Most_Common_Value': 'Column Not Found',
                    'Usability': 'Not Available'
                })
        
        self.df_delay_risk = pd.DataFrame(delay_risk_analysis)
        self.df_delay_risk.to_csv(self.output_dir / 'xlsb_delay_risk_analysis.csv', index=False)
        
    def generate_provenance_document(self):
        
        operational_cols = self.df_categorization[self.df_categorization['Category'] == 'Operational']['Column'].tolist()
        engineered_cols = self.df_categorization[self.df_categorization['Category'] == 'Engineered/Template']['Column'].tolist()
        
        high_missing = self.df_quality[self.df_quality['Missing_Pct'] > 50]['Column'].tolist()
        high_constant = self.df_quality[self.df_quality['Constant_Pct'] > 90]['Column'].tolist()
        
        delay_risk_summary = self.df_delay_risk[['Field', 'Missing_Pct', 'Constant_Pct', 'Usability']].to_string(index=False)
        
        doc_content = f"""# FedEx .xlsb Extract - Provenance & Usability Assessment

**File:** `Fedex data version 1 (1).xlsb`  
**Analysis Date:** {pd.Timestamp.now().strftime('%Y-%m-%d')}  
**Total Rows:** {len(self.df):,}  
**Total Columns:** {len(self.df.columns)}

---

## 1. Column Classification

### Operational Columns ({len(operational_cols)})
Columns that appear to contain real operational/transactional data:

{self._format_column_list(operational_cols)}

### Engineered/Template Columns ({len(engineered_cols)})
Columns that appear to be calculated, derived, or template fields:

{self._format_column_list(engineered_cols)}

---

## 2. Data Quality Concerns

### High Missing Data (>50%)
The following columns have more than 50% missing values:

{self._format_column_list(high_missing) if high_missing else "None"}

### Constant/Invariant Columns (>90%)
The following columns have >90% constant values (low variance):

{self._format_column_list(high_constant) if high_constant else "None"}

---

## 3. Delay/Risk Field Analysis

Key fields relevant to delay probability and severity modeling:

```
{delay_risk_summary}
```

### Critical Findings:
- **High Usability:** {(self.df_delay_risk['Usability'] == 'High').sum()} fields
- **Medium Usability:** {(self.df_delay_risk['Usability'] == 'Medium').sum()} fields
- **Low Usability:** {(self.df_delay_risk['Usability'] == 'Low').sum()} fields
- **Not Available:** {(self.df_delay_risk['Usability'] == 'Not Available').sum()} fields

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
"""
        
        doc_path = Path('docs') / 'xlsb_provenance_usability.md'
        with open(doc_path, 'w', encoding='utf-8') as f:
            f.write(doc_content)
        
    def _format_column_list(self, columns):
        if not columns:
            return "None"
        return '\n'.join([f"- {col}" for col in columns[:20]]) + (f"\n- ... and {len(columns)-20} more" if len(columns) > 20 else "")
    
    def run_analysis(self):
        self.load_data()
        self.categorize_columns()
        self.analyze_data_quality()
        self.analyze_delay_risk_fields()
        self.generate_provenance_document()
        print("Analysis complete.")



if __name__ == "__main__":
    analyzer = XLSBAnalyzer(
        xlsb_file='Fedex data version 1 (1).xlsb',
        output_dir='reports/data_readiness/qa_outputs'
    )
    
    analyzer.run_analysis()
