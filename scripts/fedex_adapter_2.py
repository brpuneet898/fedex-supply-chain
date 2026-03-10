import pandas as pd
from pathlib import Path


class FedexDataAdapter:
    
    def __init__(self, data_dir='.'):
        self.data_dir = Path(data_dir)
        self.df_weekly = None
        self.df_aug = None
        self.df_xlsb = None
        
    def load_weekly(self, filename='Weekly 202201-202412(1).xlsx'):
        filepath = self.data_dir / filename
        self.df_weekly = pd.read_excel(filepath)
        self.df_weekly['shp_dt'] = pd.to_datetime(self.df_weekly['shp_dt'], errors='coerce')
        return self.df_weekly
    
    def load_aug(self, filename='Aug actuals with DOM (1).xlsx'):
        filepath = self.data_dir / filename
        self.df_aug = pd.read_excel(filepath)
        self.df_aug['ShipDate'] = pd.to_datetime(self.df_aug['ShipDate'], errors='coerce')
        return self.df_aug
    
    def load_xlsb(self, filename='Fedex data version 1 (1).xlsb'):
        filepath = self.data_dir / filename
        self.df_xlsb = pd.read_excel(filepath, engine='pyxlsb')
        return self.df_xlsb
    
    def apply_lane_recovery_rule(self, df):
        if 'Lane_' in df.columns and 'Lane' in df.columns:
            mask = df['Lane_'].isna() & (df['Lane'] == 'Americas')
            df.loc[mask, 'Lane_'] = 'LA'
        return df
    
    def harmonize_lanes(self, df, lane_col='Lane_'):
        lane_mapping = {
            'EU': 'Europe',
            'AS': 'APAC',
            'ME': 'MEISA',
            'LA': 'Americas'
        }
        if lane_col in df.columns:
            df[lane_col] = df[lane_col].map(lane_mapping).fillna(df[lane_col])
        return df
    
    def map_aug_to_bronze(self, df):
        df = self.apply_lane_recovery_rule(df)
        df = self.harmonize_lanes(df, 'Lane_')
        
        bronze_df = pd.DataFrame()
        bronze_df['ship_date'] = df['ShipDate']
        bronze_df['FY'] = df['ShipDate'].dt.year
        bronze_df['WeekNbr'] = df['WeekNbr'] if 'WeekNbr' in df.columns else None
        bronze_df['Orig_Ctry'] = df['Orig_Ctry']
        bronze_df['ORIG_RAMP'] = df['ORIG_RAMP']
        bronze_df['Business_Region'] = df['Business_Region']
        bronze_df['Dest_Lane'] = df['Lane_']
        bronze_df['Product_Code'] = df['Product']
        bronze_df['PACKS'] = df['Packs']
        bronze_df['Shipments'] = df['Shipments']
        bronze_df['aPounds'] = df['aLbs']
        
        return bronze_df
    
    def map_weekly_to_bronze(self, df):
        df = self.harmonize_lanes(df, 'Dest_Lane')
        
        bronze_df = pd.DataFrame()
        bronze_df['ship_date'] = df['shp_dt']
        bronze_df['FY'] = df['FY']
        bronze_df['WeekNbr'] = df['WeekNbr']
        bronze_df['Orig_Ctry'] = df['Orig_Ctry']
        bronze_df['ORIG_RAMP'] = df['ORIG_RAMP']
        bronze_df['Business_Region'] = df['Business_Region']
        bronze_df['Dest_Lane'] = df['Dest_Lane']
        bronze_df['Product_Code'] = df['Product_Code']
        bronze_df['PACKS'] = df['PACKS']
        bronze_df['Shipments'] = df['Shipments']
        bronze_df['aPounds'] = df['aPounds']
        
        if 'Pounds' in df.columns:
            bronze_df['Pounds'] = df['Pounds']
        
        return bronze_df
    
    def aggregate_to_bronze(self, df):
        group_cols = ['ship_date', 'FY', 'WeekNbr', 'Orig_Ctry', 'ORIG_RAMP', 
                     'Business_Region', 'Dest_Lane', 'Product_Code']
        
        agg_dict = {
            'PACKS': 'sum',
            'Shipments': 'sum',
            'aPounds': 'sum'
        }
        
        if 'Pounds' in df.columns:
            agg_dict['Pounds'] = 'sum'
        
        bronze_agg = df.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()
        return bronze_agg
    
    def create_bronze_table(self, aggregate_aug=True):
        if self.df_weekly is None:
            self.load_weekly()
        if self.df_aug is None:
            self.load_aug()
        
        bronze_weekly = self.map_weekly_to_bronze(self.df_weekly)
        bronze_aug = self.map_aug_to_bronze(self.df_aug)
        
        if aggregate_aug:
            bronze_aug = self.aggregate_to_bronze(bronze_aug)
        
        bronze_combined = pd.concat([bronze_weekly, bronze_aug], ignore_index=True)
        bronze_combined = bronze_combined.sort_values('ship_date')
        
        return bronze_combined


def load_fedex_data(data_dir='.', source='weekly'):
    adapter = FedexDataAdapter(data_dir)
    
    if source == 'weekly':
        return adapter.load_weekly()
    elif source == 'aug':
        return adapter.load_aug()
    elif source == 'xlsb':
        return adapter.load_xlsb()
    else:
        raise ValueError(f"Unknown source: {source}")


def create_bronze_kpi_table(data_dir='.'):
    adapter = FedexDataAdapter(data_dir)
    return adapter.create_bronze_table()
