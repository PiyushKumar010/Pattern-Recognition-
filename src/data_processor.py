import pandas as pd
from openpyxl import load_workbook

def load_and_process_data(uploaded_file):
    """
    Load the uploaded Excel file preserving original date formats as strings.
    This prevents automatic date parsing and allows user to control date parsing explicitly.
    """
    try:
        # First, load the file normally to detect datetime columns
        df_temp = pd.read_excel(uploaded_file, header=0)
        print(f"After reading Excel: {len(df_temp)} rows")
        
        empty_rows = df_temp.isnull().all(axis=1).sum()
        print(f"Completely empty rows found: {empty_rows}")
        
        # Identify datetime columns
        datetime_columns = []
        for col in df_temp.columns:
            if pd.api.types.is_datetime64_any_dtype(df_temp[col]):
                datetime_columns.append(col)
        
        # Now reload with datetime columns as strings
        if datetime_columns:
            # Create dtype dict - datetime columns as str, others inferred
            dtype_dict = {col: str for col in datetime_columns}
            df = pd.read_excel(uploaded_file, header=0, dtype=dtype_dict)
            
            # Convert datetime strings to display format (DD-MM-YYYY HH:MM:SS)
            for col in datetime_columns:
                try:
                    # Parse the datetime strings and reformat them with time component
                    df[col] = pd.to_datetime(df[col], format='ISO8601', errors='coerce').dt.strftime('%d-%m-%Y %H:%M:%S')
                    # Replace NaT with empty string
                    df[col] = df[col].fillna('')
                except:
                    pass  # Keep as is if conversion fails
        else:
            df = df_temp
        
        # Convert pure numeric columns to numeric types
        for col in df.columns:
            # Skip datetime columns (already handled)
            if col in datetime_columns:
                continue
            
            # Skip if column is empty
            sample_values = df[col].dropna()
            if len(sample_values) == 0:
                continue
            
            # Try to convert to numeric if possible (for pure numeric columns)
            try:
                numeric_converted = pd.to_numeric(df[col], errors='coerce')
                # Only convert if at least some values are actually numeric
                if numeric_converted.notna().sum() > 0:
                    # Check if conversion makes sense (not all NaN after conversion)
                    non_null_count = len(df[col].dropna())
                    if non_null_count > 0 and numeric_converted.notna().sum() / non_null_count > 0.8:
                        df[col] = numeric_converted
            except:
                pass  # Keep as string if conversion fails
        
        return df
        
    except Exception as e:
        raise Exception(f"Error loading Excel file: {str(e)}")