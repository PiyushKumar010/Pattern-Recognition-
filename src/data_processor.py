import pandas as pd
from openpyxl import load_workbook

def load_and_process_data(uploaded_file):
    """
    Load the uploaded Excel file preserving original date formats as strings.
    This prevents automatic date parsing and allows user to control date parsing explicitly.
    """
    try:
        # Use openpyxl to read the Excel file and preserve original formatting
        uploaded_file.seek(0)  # Reset file pointer
        wb = load_workbook(uploaded_file, data_only=True)
        ws = wb.active
        
        # Track which columns are date columns (by column index)
        date_column_indices = set()
        
        # Read data preserving original cell formats
        data = []
        for row_idx, row in enumerate(ws.iter_rows(values_only=False)):
            row_data = []
            for col_idx, cell in enumerate(row):
                # Get the formatted value as it appears in Excel
                if cell.value is not None:
                    # If cell has a number format (date/time), use the displayed value
                    if hasattr(cell, 'number_format') and cell.number_format and cell.number_format != 'General':
                        # Try to get the formatted string value
                        try:
                            from openpyxl.styles.numbers import is_date_format
                            if is_date_format(cell.number_format):
                                # Track this column as a date column
                                date_column_indices.add(col_idx)
                                
                                # For date cells, format them according to their Excel format
                                if isinstance(cell.value, (int, float)):
                                    # Excel serial date - convert to datetime then format
                                    from datetime import datetime, timedelta
                                    excel_date = datetime(1899, 12, 30) + timedelta(days=cell.value)
                                    # Format based on number_format
                                    if 'h' in cell.number_format.lower() or 'm' in cell.number_format.lower() or 's' in cell.number_format.lower():
                                        # Has time component
                                        row_data.append(excel_date.strftime('%d-%m-%Y %H:%M:%S'))
                                    else:
                                        # Date only
                                        row_data.append(excel_date.strftime('%d-%m-%Y'))
                                else:
                                    # Already a datetime object
                                    if 'h' in cell.number_format.lower() or 'm' in cell.number_format.lower() or 's' in cell.number_format.lower():
                                        row_data.append(cell.value.strftime('%d-%m-%Y %H:%M:%S'))
                                    else:
                                        row_data.append(cell.value.strftime('%d-%m-%Y'))
                            else:
                                row_data.append(cell.value)
                        except:
                            row_data.append(cell.value)
                    else:
                        row_data.append(cell.value)
                else:
                    row_data.append(None)
            data.append(row_data)
        
        # Convert to DataFrame
        df = pd.DataFrame(data[1:], columns=data[0])  # First row is header
        
        # Store date column names as metadata
        date_column_names = [data[0][idx] for idx in date_column_indices if idx < len(data[0])]
        df.attrs['date_columns'] = date_column_names
        
        print(f"After reading Excel: {len(df)} rows")
        print(f"Detected date columns: {date_column_names}")
        
        empty_rows = df.isnull().all(axis=1).sum()
        print(f"Completely empty rows found: {empty_rows}")
        
        # Convert pure numeric columns to numeric types (excluding date columns which are now strings)
        for col in df.columns:
            # Skip if column is empty
            sample_values = df[col].dropna()
            if len(sample_values) == 0:
                continue
            
            # Skip columns that look like dates (already preserved as strings)
            sample_str = str(sample_values.iloc[0]) if len(sample_values) > 0 else ""
            if '-' in sample_str or '/' in sample_str or ':' in sample_str:
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