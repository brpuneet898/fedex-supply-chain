import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


class FedexDataValidator:
    
    def __init__(self, weekly_file, aug_file, xlsb_file, output_dir):
        self.weekly_file = weekly_file
        self.aug_file = aug_file
        self.xlsb_file = xlsb_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.weekly_required_cols = ['shp_dt', 'WeekNbr', 'Orig_Ctry', 'ORIG_RAMP', 
                                      'Business_Region', 'Dest_Lane', 'FY', 'Product_Code',
                                      'PACKS', 'Shipments', 'aPounds']
        
        self.aug_required_cols = ['ShipDate', 'WeekNbr', 'Orig_Ctry', 'ORIG_RAMP',
                                   'Business_Region', 'Lane_', 'Product',
                                   'Packs', 'Shipments', 'aLbs']
        
        self.aug_customer_exceptions = ['ShipperCustomer', 'PayerCustomer', 
                                         'SHIPPER_GLOBAL_NAME', 'PAYER_GLOBAL_NAME']
        
        self.results = {}
        
    def load_data(self):
        self.df_weekly = pd.read_excel(self.weekly_file)
        self.df_aug = pd.read_excel(self.aug_file)
        self.df_xlsb = pd.read_excel(self.xlsb_file, engine='pyxlsb')
        
    def schema_type_checks(self):
        schema_results = []
        
        missing_cols_weekly = [col for col in self.weekly_required_cols if col not in self.df_weekly.columns]
        missing_cols_aug = [col for col in self.aug_required_cols if col not in self.df_aug.columns]
        
        schema_results.append({
            'Dataset': 'Weekly',
            'Check': 'Missing Required Columns',
            'Result': 'PASS' if not missing_cols_weekly else 'FAIL',
            'Details': str(missing_cols_weekly) if missing_cols_weekly else 'All required columns present'
        })
        
        schema_results.append({
            'Dataset': 'Aug',
            'Check': 'Missing Required Columns',
            'Result': 'PASS' if not missing_cols_aug else 'FAIL',
            'Details': str(missing_cols_aug) if missing_cols_aug else 'All required columns present'
        })
        
        self.df_weekly['shp_dt'] = pd.to_datetime(self.df_weekly['shp_dt'], errors='coerce')
        unparseable_dates_weekly = self.df_weekly['shp_dt'].isna().sum()
        
        self.df_aug['ShipDate'] = pd.to_datetime(self.df_aug['ShipDate'], errors='coerce')
        unparseable_dates_aug = self.df_aug['ShipDate'].isna().sum()
        
        schema_results.append({
            'Dataset': 'Weekly',
            'Check': 'Date Parsing (shp_dt)',
            'Result': 'PASS' if unparseable_dates_weekly == 0 else 'WARNING',
            'Details': f'{unparseable_dates_weekly} unparseable dates'
        })
        
        schema_results.append({
            'Dataset': 'Aug',
            'Check': 'Date Parsing (ShipDate)',
            'Result': 'PASS' if unparseable_dates_aug == 0 else 'WARNING',
            'Details': f'{unparseable_dates_aug} unparseable dates'
        })
        
        numeric_cols_weekly = ['PACKS', 'Shipments', 'aPounds', 'Pounds']
        for col in numeric_cols_weekly:
            if col in self.df_weekly.columns:
                is_numeric = pd.api.types.is_numeric_dtype(self.df_weekly[col])
                schema_results.append({
                    'Dataset': 'Weekly',
                    'Check': f'Numeric Type ({col})',
                    'Result': 'PASS' if is_numeric else 'FAIL',
                    'Details': f'dtype: {self.df_weekly[col].dtype}'
                })
        
        numeric_cols_aug = ['Packs', 'Shipments', 'aLbs']
        for col in numeric_cols_aug:
            if col in self.df_aug.columns:
                is_numeric = pd.api.types.is_numeric_dtype(self.df_aug[col])
                schema_results.append({
                    'Dataset': 'Aug',
                    'Check': f'Numeric Type ({col})',
                    'Result': 'PASS' if is_numeric else 'FAIL',
                    'Details': f'dtype: {self.df_aug[col].dtype}'
                })
        
        df_schema = pd.DataFrame(schema_results)
        df_schema.to_csv(self.output_dir / 'schema_type_checks.csv', index=False)
        self.results['schema'] = df_schema
        
    def missingness_analysis(self):
        missingness_weekly = []
        for col in self.df_weekly.columns:
            missing_count = self.df_weekly[col].isna().sum()
            missing_pct = (missing_count / len(self.df_weekly)) * 100
            missingness_weekly.append({
                'Dataset': 'Weekly',
                'Column': col,
                'Missing_Count': missing_count,
                'Missing_Pct': round(missing_pct, 2),
                'Total_Rows': len(self.df_weekly)
            })
        
        missingness_aug = []
        for col in self.df_aug.columns:
            missing_count = self.df_aug[col].isna().sum()
            missing_pct = (missing_count / len(self.df_aug)) * 100
            is_exception = col in self.aug_customer_exceptions
            missingness_aug.append({
                'Dataset': 'Aug',
                'Column': col,
                'Missing_Count': missing_count,
                'Missing_Pct': round(missing_pct, 2),
                'Total_Rows': len(self.df_aug),
                'Exception': 'Customer Field (Allowed)' if is_exception else ''
            })
        
        df_miss_weekly = pd.DataFrame(missingness_weekly)
        df_miss_aug = pd.DataFrame(missingness_aug)
        df_miss_combined = pd.concat([df_miss_weekly, df_miss_aug], ignore_index=True)
        
        df_miss_combined.to_csv(self.output_dir / 'missingness_analysis.csv', index=False)
        self.results['missingness'] = df_miss_combined
    
    def non_negativity_checks(self):
        neg_results = []
        
        weekly_volume_cols = ['PACKS', 'Shipments', 'aPounds', 'Pounds']
        for col in weekly_volume_cols:
            if col in self.df_weekly.columns:
                neg_count = (self.df_weekly[col] < 0).sum()
                neg_results.append({
                    'Dataset': 'Weekly',
                    'Column': col,
                    'Negative_Count': neg_count,
                    'Result': 'PASS' if neg_count == 0 else 'FAIL'
                })
        
        aug_volume_cols = ['Packs', 'Shipments', 'aLbs']
        for col in aug_volume_cols:
            if col in self.df_aug.columns:
                neg_count = (self.df_aug[col] < 0).sum()
                neg_results.append({
                    'Dataset': 'Aug',
                    'Column': col,
                    'Negative_Count': neg_count,
                    'Result': 'PASS' if neg_count == 0 else 'FAIL'
                })
        
        df_neg = pd.DataFrame(neg_results)
        df_neg.to_csv(self.output_dir / 'non_negativity_checks.csv', index=False)
        self.results['negativity'] = df_neg
    
    def plausibility_checks(self):
        
        self.df_weekly['lbs_per_pack'] = self.df_weekly['aPounds'] / self.df_weekly['PACKS']
        self.df_weekly['lbs_per_pack'] = self.df_weekly['lbs_per_pack'].replace([np.inf, -np.inf], np.nan)
        
        self.df_aug['lbs_per_pack'] = self.df_aug['aLbs'] / self.df_aug['Packs']
        self.df_aug['lbs_per_pack'] = self.df_aug['lbs_per_pack'].replace([np.inf, -np.inf], np.nan)
        
        weekly_outliers = []
        for product in self.df_weekly['Product_Code'].unique():
            if pd.isna(product):
                continue
            product_data = self.df_weekly[self.df_weekly['Product_Code'] == product]['lbs_per_pack'].dropna()
            if len(product_data) > 0:
                q1 = product_data.quantile(0.25)
                q3 = product_data.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 3 * iqr
                upper_bound = q3 + 3 * iqr
                
                outlier_mask = ((self.df_weekly['Product_Code'] == product) & 
                                ((self.df_weekly['lbs_per_pack'] < lower_bound) | 
                                 (self.df_weekly['lbs_per_pack'] > upper_bound)))
                
                if outlier_mask.sum() > 0:
                    weekly_outliers.append({
                        'Dataset': 'Weekly',
                        'Product': product,
                        'Outlier_Count': outlier_mask.sum(),
                        'Median_lbs_per_pack': round(product_data.median(), 2),
                        'Q1': round(q1, 2),
                        'Q3': round(q3, 2),
                        'Lower_Bound': round(lower_bound, 2),
                        'Upper_Bound': round(upper_bound, 2)
                    })
        
        aug_outliers = []
        for product in self.df_aug['Product'].unique():
            if pd.isna(product):
                continue
            product_data = self.df_aug[self.df_aug['Product'] == product]['lbs_per_pack'].dropna()
            if len(product_data) > 0:
                q1 = product_data.quantile(0.25)
                q3 = product_data.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 3 * iqr
                upper_bound = q3 + 3 * iqr
                
                outlier_mask = ((self.df_aug['Product'] == product) & 
                                ((self.df_aug['lbs_per_pack'] < lower_bound) | 
                                 (self.df_aug['lbs_per_pack'] > upper_bound)))
                
                if outlier_mask.sum() > 0:
                    aug_outliers.append({
                        'Dataset': 'Aug',
                        'Product': product,
                        'Outlier_Count': outlier_mask.sum(),
                        'Median_lbs_per_pack': round(product_data.median(), 2),
                        'Q1': round(q1, 2),
                        'Q3': round(q3, 2),
                        'Lower_Bound': round(lower_bound, 2),
                        'Upper_Bound': round(upper_bound, 2)
                    })
        
        df_outliers = pd.DataFrame(weekly_outliers + aug_outliers)
        df_outliers.to_csv(self.output_dir / 'plausibility_outliers.csv', index=False)
        self.results['outliers'] = df_outliers
    
    def reconciliation_checks(self):
        
        df_weekly_aug = self.df_weekly[
            (self.df_weekly['shp_dt'] >= '2024-08-01') & 
            (self.df_weekly['shp_dt'] < '2024-09-01')
        ].copy()
        
        df_aug_2024 = self.df_aug[
            (self.df_aug['ShipDate'] >= '2024-08-01') & 
            (self.df_aug['ShipDate'] < '2024-09-01')
        ].copy()
        
        df_aug_2024['Dest_Lane'] = df_aug_2024['Lane_']
        df_aug_2024['Product_Code'] = df_aug_2024['Product']
        df_aug_2024['PACKS'] = df_aug_2024['Packs']
        df_aug_2024['aPounds'] = df_aug_2024['aLbs']
        
        if 'FY' not in df_aug_2024.columns:
            df_aug_2024['FY'] = df_aug_2024['ShipDate'].dt.year
        
        bronze_keys = ['Orig_Ctry', 'ORIG_RAMP', 'Business_Region', 'Dest_Lane', 'Product_Code']
        
        weekly_agg = df_weekly_aug.groupby(bronze_keys, dropna=False).agg({
            'PACKS': 'sum',
            'Shipments': 'sum',
            'aPounds': 'sum'
        }).reset_index()
        weekly_agg.columns = bronze_keys + ['PACKS_Weekly', 'Shipments_Weekly', 'aPounds_Weekly']
        
        aug_agg = df_aug_2024.groupby(bronze_keys, dropna=False).agg({
            'PACKS': 'sum',
            'Shipments': 'sum',
            'aPounds': 'sum'
        }).reset_index()
        aug_agg.columns = bronze_keys + ['PACKS_Aug', 'Shipments_Aug', 'aPounds_Aug']
        
        reconciliation = pd.merge(weekly_agg, aug_agg, on=bronze_keys, how='outer')
        reconciliation = reconciliation.fillna(0)
        
        reconciliation['PACKS_Delta'] = reconciliation['PACKS_Aug'] - reconciliation['PACKS_Weekly']
        reconciliation['PACKS_Delta_Pct'] = np.where(
            reconciliation['PACKS_Weekly'] != 0,
            (reconciliation['PACKS_Delta'] / reconciliation['PACKS_Weekly']) * 100,
            np.nan
        )
        
        reconciliation['Shipments_Delta'] = reconciliation['Shipments_Aug'] - reconciliation['Shipments_Weekly']
        reconciliation['Shipments_Delta_Pct'] = np.where(
            reconciliation['Shipments_Weekly'] != 0,
            (reconciliation['Shipments_Delta'] / reconciliation['Shipments_Weekly']) * 100,
            np.nan
        )
        
        reconciliation['aPounds_Delta'] = reconciliation['aPounds_Aug'] - reconciliation['aPounds_Weekly']
        reconciliation['aPounds_Delta_Pct'] = np.where(
            reconciliation['aPounds_Weekly'] != 0,
            (reconciliation['aPounds_Delta'] / reconciliation['aPounds_Weekly']) * 100,
            np.nan
        )
        
        reconciliation.to_csv(self.output_dir / 'reconciliation_aug_vs_weekly.csv', index=False)
        
        lane_summary = reconciliation.groupby('Dest_Lane', dropna=False).agg({
            'PACKS_Weekly': 'sum',
            'PACKS_Aug': 'sum',
            'PACKS_Delta': 'sum',
            'Shipments_Weekly': 'sum',
            'Shipments_Aug': 'sum',
            'Shipments_Delta': 'sum',
            'aPounds_Weekly': 'sum',
            'aPounds_Aug': 'sum',
            'aPounds_Delta': 'sum'
        }).reset_index()
        
        lane_summary['PACKS_Delta_Pct'] = np.where(
            lane_summary['PACKS_Weekly'] != 0,
            (lane_summary['PACKS_Delta'] / lane_summary['PACKS_Weekly']) * 100,
            np.nan
        )
        lane_summary['Shipments_Delta_Pct'] = np.where(
            lane_summary['Shipments_Weekly'] != 0,
            (lane_summary['Shipments_Delta'] / lane_summary['Shipments_Weekly']) * 100,
            np.nan
        )
        lane_summary['aPounds_Delta_Pct'] = np.where(
            lane_summary['aPounds_Weekly'] != 0,
            (lane_summary['aPounds_Delta'] / lane_summary['aPounds_Weekly']) * 100,
            np.nan
        )
        
        lane_summary.to_csv(self.output_dir / 'reconciliation_by_lane.csv', index=False)
        
        product_summary = reconciliation.groupby('Product_Code', dropna=False).agg({
            'PACKS_Weekly': 'sum',
            'PACKS_Aug': 'sum',
            'PACKS_Delta': 'sum',
            'Shipments_Weekly': 'sum',
            'Shipments_Aug': 'sum',
            'Shipments_Delta': 'sum',
            'aPounds_Weekly': 'sum',
            'aPounds_Aug': 'sum',
            'aPounds_Delta': 'sum'
        }).reset_index()
        
        product_summary['PACKS_Delta_Pct'] = np.where(
            product_summary['PACKS_Weekly'] != 0,
            (product_summary['PACKS_Delta'] / product_summary['PACKS_Weekly']) * 100,
            np.nan
        )
        product_summary['Shipments_Delta_Pct'] = np.where(
            product_summary['Shipments_Weekly'] != 0,
            (product_summary['Shipments_Delta'] / product_summary['Shipments_Weekly']) * 100,
            np.nan
        )
        product_summary['aPounds_Delta_Pct'] = np.where(
            product_summary['aPounds_Weekly'] != 0,
            (product_summary['aPounds_Delta'] / product_summary['aPounds_Weekly']) * 100,
            np.nan
        )
        
        product_summary.to_csv(self.output_dir / 'reconciliation_by_product.csv', index=False)
        
        ramp_summary = reconciliation.groupby('ORIG_RAMP', dropna=False).agg({
            'PACKS_Weekly': 'sum',
            'PACKS_Aug': 'sum',
            'PACKS_Delta': 'sum',
            'Shipments_Weekly': 'sum',
            'Shipments_Aug': 'sum',
            'Shipments_Delta': 'sum',
            'aPounds_Weekly': 'sum',
            'aPounds_Aug': 'sum',
            'aPounds_Delta': 'sum'
        }).reset_index()
        
        ramp_summary['PACKS_Delta_Pct'] = np.where(
            ramp_summary['PACKS_Weekly'] != 0,
            (ramp_summary['PACKS_Delta'] / ramp_summary['PACKS_Weekly']) * 100,
            np.nan
        )
        ramp_summary['Shipments_Delta_Pct'] = np.where(
            ramp_summary['Shipments_Weekly'] != 0,
            (ramp_summary['Shipments_Delta'] / ramp_summary['Shipments_Weekly']) * 100,
            np.nan
        )
        ramp_summary['aPounds_Delta_Pct'] = np.where(
            ramp_summary['aPounds_Weekly'] != 0,
            (ramp_summary['aPounds_Delta'] / ramp_summary['aPounds_Weekly']) * 100,
            np.nan
        )
        
        ramp_summary.to_csv(self.output_dir / 'reconciliation_by_ramp.csv', index=False)
        
        self.results['reconciliation'] = reconciliation
        self.results['recon_lane'] = lane_summary
        self.results['recon_product'] = product_summary
        self.results['recon_ramp'] = ramp_summary
        
    def run_all_checks(self):
        self.load_data()
        self.schema_type_checks()
        self.missingness_analysis()
        self.non_negativity_checks()
        self.plausibility_checks()
        self.reconciliation_checks()
        print("Validation complete.")


if __name__ == "__main__":
    validator = FedexDataValidator(
        weekly_file='Weekly 202201-202412(1).xlsx',
        aug_file='Aug actuals with DOM (1).xlsx',
        xlsb_file='Fedex data version 1 (1).xlsb',
        output_dir='reports/data_readiness/qa_outputs'
    )
    
    validator.run_all_checks()
