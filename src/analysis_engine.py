import pandas as pd
import numpy as np
from itertools import combinations, product
from datetime import datetime
from src.data_processor import fetch_dataframe_from_db
from src.filter_manager import generate_sql_condition


def analyze_data_combinations_db(table_name, selected_columns, thresholds, id_column, result_columns, 
                                  column_types, min_matching_rows=10):
    """
    Database-driven version: Analyze data combinations using SQL queries for better performance.
    Fetches data from PostgreSQL instead of working on pandas DataFrames.
    
    Args:
        table_name (str): Name of the database table containing the data
        selected_columns (list): Columns to analyze
        thresholds (dict): Threshold configurations
        id_column (str): ID column name
        result_columns (list): Columns to calculate statistics for
        column_types (dict): Column data types {'column_name': 'numeric'/'date'/'categorical'}
        min_matching_rows (int): Minimum number of rows required for a combination
    
    Returns:
        pd.DataFrame: Analysis results
    """
    results = []
    
    # Generate all combination lengths
    for combo_length in range(1, len(selected_columns) + 1):
        # Get all combinations of columns for this length
        for column_combo in combinations(selected_columns, combo_length):
            
            # For each combination, generate all condition variations
            condition_variations = []
            for col in column_combo:
                threshold_config = thresholds[col]
                col_type = column_types.get(col, 'numeric')
                
                # Generate SQL conditions for this column
                sql_conditions = generate_sql_condition(col, threshold_config, col_type)
                
                # Store as tuples with metadata for later use
                condition_tuples = []
                for sql_cond in sql_conditions:
                    condition_tuples.append((col, sql_cond, threshold_config, col_type))
                
                condition_variations.append(condition_tuples)
            
            # Generate all products of condition variations
            for condition_set in product(*condition_variations):
                # Build SQL query for this combination
                where_clauses = []
                applied_conditions = {}
                
                # Initialize all selected columns as blank
                for col in selected_columns:
                    applied_conditions[col] = ""
                
                # Build WHERE clause
                for col, sql_cond, threshold_cfg, col_type in condition_set:
                    where_clauses.append(f"({sql_cond})")
                    applied_conditions[col] = generate_condition_description(col, sql_cond, threshold_cfg, col_type)
                
                # Combine WHERE clauses
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                # Build aggregation SQL query
                agg_parts = [f"COUNT(*) as matching_rows"]
                
                for result_col in result_columns:
                    agg_parts.extend([
                        f"AVG(\"{result_col}\") as {result_col}_mean",
                        f"SUM(\"{result_col}\") as {result_col}_sum",
                        f"COUNT(\"{result_col}\") as {result_col}_count",
                        f"STDDEV(\"{result_col}\") as {result_col}_stddev",
                        f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY \"{result_col}\") as {result_col}_median",
                        f"MIN(\"{result_col}\") as {result_col}_min",
                        f"MAX(\"{result_col}\") as {result_col}_max"
                    ])
                
                # Build and execute aggregation query
                agg_query = f"""
                    SELECT {', '.join(agg_parts)}
                    FROM {table_name}
                    WHERE {where_clause}
                """
                
                try:
                    agg_df = fetch_dataframe_from_db(agg_query)
                    
                    if agg_df is not None and not agg_df.empty:
                        matching_rows = int(agg_df.iloc[0]['matching_rows'])
                        
                        # Skip if below minimum threshold
                        if matching_rows < min_matching_rows:
                            continue
                        
                        # Create result row
                        result_row = applied_conditions.copy()
                        result_row['Matching_Rows'] = matching_rows
                        
                        # Add aggregated statistics
                        for col in agg_df.columns:
                            if col != 'matching_rows':
                                val = agg_df.iloc[0][col]
                                if pd.notna(val):
                                    result_row[col.title().replace('_', ' ')] = round(float(val), 4) if isinstance(val, (int, float)) else val
                        
                        # Fetch sample IDs (limited to first 20)
                        id_query = f"""
                            SELECT \"{id_column}\"
                            FROM {table_name}
                            WHERE {where_clause}
                            LIMIT 20
                        """
                        
                        id_df = fetch_dataframe_from_db(id_query)
                        if id_df is not None and not id_df.empty:
                            ids = id_df[id_column].astype(str).tolist()
                            if matching_rows > 20:
                                result_row['IDs'] = ', '.join(ids) + f" ... ({matching_rows - 20} more)"
                            else:
                                result_row['IDs'] = ', '.join(ids)
                        
                        results.append(result_row)
                        
                except Exception as e:
                    print(f"Error executing query: {e}")
                    print(f"Query: {agg_query}")
                    continue
    
    return pd.DataFrame(results)


def generate_condition_description(column, sql_condition, threshold_config, col_type):
    """
    Generate human-readable description from SQL condition.
    
    Args:
        column (str): Column name
        sql_condition (str): SQL condition string
        threshold_config (dict): Original threshold configuration
        col_type (str): Column type
    
    Returns:
        str: Human-readable description
    """
    # Extract key information from SQL condition or use threshold config
    if col_type == 'date':
        if 'BETWEEN' in sql_condition:
            parts = sql_condition.split("BETWEEN")[1].split("AND")
            if len(parts) == 2:
                start = parts[0].strip().strip("'")
                end = parts[1].strip().strip("'")
                return f"{column}: {start} to {end}"
        elif '<' in sql_condition and '::date' in sql_condition:
            date = sql_condition.split("'")[1]
            return f"{column} before {date}"
        elif '>' in sql_condition and '::date' in sql_condition:
            date = sql_condition.split("'")[1]
            return f"{column} after {date}"
        elif '=' in sql_condition and '::date' in sql_condition:
            date = sql_condition.split("'")[1]
            return f"{column} on {date}"
            
    elif col_type == 'numeric':
        if 'OR' in sql_condition:
            return f"{column}: {sql_condition}"
        elif '>=' in sql_condition and '<' in sql_condition:
            # Range condition
            parts = sql_condition.split('AND')
            return f"{column}: {' and '.join(parts)}"
        elif '>=' in sql_condition:
            val = sql_condition.split('>=')[1].strip()
            return f"{column} >= {val}"
        elif '<' in sql_condition:
            val = sql_condition.split('<')[1].strip()
            return f"{column} < {val}"
        elif '>' in sql_condition:
            val = sql_condition.split('>')[1].strip()
            return f"{column} > {val}"
            
    elif col_type == 'categorical':
        if 'IN' in sql_condition:
            values = sql_condition.split('IN')[1].strip().strip('()').replace("'", "")
            return f"{column} in [{values}]"
    
    # Fallback
    return sql_condition


def calculate_max_run(series: pd.Series) -> int:
    """
    Calculates the longest consecutive run (streak) of the same value in the series.
    Works for both numeric and categorical data.
    """
    if series.empty:
        return 0
    
    max_run = current_run = 1
    prev_value = series.iloc[0]
    
    for value in series.iloc[1:]:
        if value == prev_value:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
        prev_value = value
    
    return max_run

def is_date_column(df, column):
    """Check if a column contains date/datetime data"""
    # Ensure column is a string, not a list or other type
    if not isinstance(column, str):
        return False
    
    # Check if column exists
    if column not in df.columns:
        return False
    
    # Get the column - ensure we get a Series, not a DataFrame
    col_data = df[column]
    
    # If we got a DataFrame instead of Series (duplicate column names), return False
    if isinstance(col_data, pd.DataFrame):
        return False
    
    # Check if it's a datetime dtype
    if pd.api.types.is_datetime64_any_dtype(col_data):
        return True
    
    # Check if it's in the metadata (date columns preserved as strings)
    if hasattr(df, 'attrs') and 'date_columns' in df.attrs:
        if column in df.attrs['date_columns']:
            return True
    
    # Fallback: check if string column looks like dates
    if col_data.dtype == 'object':
        sample = col_data.dropna().head(10)
        if len(sample) > 0:
            # Check if values match common date patterns
            sample_str = str(sample.iloc[0])
            # Common date patterns: DD-MM-YYYY, MM-DD-YYYY, YYYY-MM-DD with optional time
            date_patterns = ['-', '/']
            if any(pattern in sample_str for pattern in date_patterns):
                # Try to parse a sample
                try:
                    pd.to_datetime(sample, errors='coerce')
                    parsed = pd.to_datetime(sample, errors='coerce')
                    # If majority can be parsed as dates, consider it a date column
                    if parsed.notna().sum() / len(sample) > 0.5:
                        return True
                except:
                    pass
    
    return False

def get_date_columns(df):
    """Get all date columns from the dataframe"""
    date_columns = []
    for col in df.columns:
        if is_date_column(df, col):
            date_columns.append(col)
    return date_columns

def apply_date_filter(df, column, threshold_config):
    """Apply date filtering based on the threshold configuration"""
    col_data = pd.to_datetime(df[column], errors='coerce')
    
    if threshold_config["type"] == "single_range":
        start_date = pd.to_datetime(threshold_config["start_date"])
        end_date = pd.to_datetime(threshold_config["end_date"])
        mask = (col_data.dt.date >= start_date.date()) & (col_data.dt.date <= end_date.date())
        return df[mask]
        
    elif threshold_config["type"] == "before":
        target_date = pd.to_datetime(threshold_config["date"])
        mask = col_data.dt.date < target_date.date()
        return df[mask]
        
    elif threshold_config["type"] == "after":
        target_date = pd.to_datetime(threshold_config["date"])
        mask = col_data.dt.date > target_date.date()
        return df[mask]
        
    elif threshold_config["type"] == "on":
        target_date = pd.to_datetime(threshold_config["date"])
        mask = col_data.dt.date == target_date.date()
        return df[mask]
        
    elif threshold_config["type"] == "last_n_days":
        cutoff_date = pd.to_datetime(threshold_config["cutoff_date"])
        mask = col_data >= cutoff_date
        return df[mask]
        
    elif threshold_config["type"] == "first_n_days":
        cutoff_date = pd.to_datetime(threshold_config["cutoff_date"])
        mask = col_data <= cutoff_date
        return df[mask]
    
    return df

def generate_date_condition_description(column, threshold_data, operator):
    """Generate human-readable description for date conditions"""
    if operator == 'single_range':
        start = pd.to_datetime(threshold_data["start_date"]).strftime('%Y-%m-%d')
        end = pd.to_datetime(threshold_data["end_date"]).strftime('%Y-%m-%d')
        return f"{column}: {start} to {end}"
        
    elif operator == 'range':
        start = pd.to_datetime(threshold_data["start_date"]).strftime('%Y-%m-%d')
        end = pd.to_datetime(threshold_data["end_date"]).strftime('%Y-%m-%d')
        return f"{column}: {start} to {end}"
        
    elif operator == 'before':
        date_str = pd.to_datetime(threshold_data).strftime('%Y-%m-%d')
        return f"{column} before {date_str}"
        
    elif operator == 'after':
        date_str = pd.to_datetime(threshold_data).strftime('%Y-%m-%d')
        return f"{column} after {date_str}"
        
    elif operator == 'on':
        date_str = pd.to_datetime(threshold_data).strftime('%Y-%m-%d')
        return f"{column} on {date_str}"
        
    elif operator == 'last_n_days':
        days = threshold_data["days"]
        cutoff = pd.to_datetime(threshold_data["cutoff_date"]).strftime('%Y-%m-%d')
        return f"{column} last {days} days (from {cutoff})"
        
    elif operator == 'first_n_days':
        days = threshold_data["days"]
        cutoff = pd.to_datetime(threshold_data["cutoff_date"]).strftime('%Y-%m-%d')
        return f"{column} first {days} days (until {cutoff})"
    
    return f"{column}: unknown date filter"

def analyze_data_combinations(df, selected_columns, thresholds, id_column, result_columns, min_matching_rows=10):
    results = []
    
    for combo_length in range(1, len(selected_columns) + 1):
        # Get all combinations of columns for this length
        for column_combo in combinations(selected_columns, combo_length):
            
            # For each combination, generate all condition variations
            condition_variations = []
            for col in column_combo:
                threshold_config = thresholds[col]
                
                if is_date_column(df, col):
                    if threshold_config["type"] == "single_range":
                        condition_variations.append([(col, threshold_config, 'single_range')])
                    elif threshold_config["type"] == "multiple_ranges":
                        range_conditions = []
                        for range_config in threshold_config["ranges"]:
                            range_conditions.append((col, range_config, 'range'))
                        condition_variations.append(range_conditions)
                    elif threshold_config["type"] == "multiple_before":
                        before_conditions = []
                        for date in threshold_config["dates"]:
                            before_conditions.append((col, date, 'before'))
                        condition_variations.append(before_conditions)
                    elif threshold_config["type"] == "multiple_after":
                        after_conditions = []
                        for date in threshold_config["dates"]:
                            after_conditions.append((col, date, 'after'))
                        condition_variations.append(after_conditions)
                    elif threshold_config["type"] == "multiple_on":
                        on_conditions = []
                        for date in threshold_config["dates"]:
                            on_conditions.append((col, date, 'on'))
                        condition_variations.append(on_conditions)
                    elif threshold_config["type"] == "multiple_last_n_days":
                        last_n_conditions = []
                        for config in threshold_config["configs"]:
                            last_n_conditions.append((col, config, 'last_n_days'))
                        condition_variations.append(last_n_conditions)
                    elif threshold_config["type"] == "multiple_first_n_days":
                        first_n_conditions = []
                        for config in threshold_config["configs"]:
                            first_n_conditions.append((col, config, 'first_n_days'))
                        condition_variations.append(first_n_conditions)

                elif pd.api.types.is_numeric_dtype(df[col]):
                    if threshold_config["type"] == "range":
                        # For range: create conditions for each range
                        range_conditions = []
                        for i, (start, end) in enumerate(threshold_config["ranges"]):
                            range_conditions.append(
                                (col, {"start": start, "end": end, "range_id": i+1, "total_ranges": len(threshold_config["ranges"])}, 'range')
                            )
                        condition_variations.append(range_conditions)
                    elif threshold_config["type"] == "multiple_greater_than":
                        # Create conditions for each greater than value
                        multiple_greater_conditions = []
                        for value in threshold_config["values"]:
                            multiple_greater_conditions.append(
                                (col, value, '>')
                            )
                        condition_variations.append(multiple_greater_conditions)
                    elif threshold_config["type"] == "multiple_less_than":
                        multiple_less_conditions = []
                        for value in threshold_config["values"]:
                            multiple_less_conditions.append(
                                (col, value, '<')
                            )
                        condition_variations.append(multiple_less_conditions)
                    elif threshold_config["type"] == "multiple_conditions_or":
                        # Create individual conditions AND the combined OR condition
                        individual_conditions = []
                        for condition in threshold_config["conditions"]:
                            # Each individual condition as a single tuple
                            individual_conditions.append(
                                (col, condition["value"], condition["operator"])
                            )
                        
                        # Add the combined OR condition as well (as a list of tuples)
                        or_condition_group = []
                        for condition in threshold_config["conditions"]:
                            or_condition_group.append(
                                (col, condition["value"], condition["operator"])
                            )
                        individual_conditions.append(or_condition_group)
                        
                        condition_variations.append(individual_conditions)
                    else:  # mean, median, custom
                        # For traditional thresholds: both >= and < conditions
                        condition_variations.append([
                            (col, threshold_config["value"], '>='),
                            (col, threshold_config["value"], '<')
                        ])
                else:
                    # For categorical: include condition with multiple value groups
                    if threshold_config["type"] == "categorical" and threshold_config["value_groups"]:
                        group_conditions = []
                        for group in threshold_config["value_groups"]:
                            if group:  # Only if group has values
                                group_conditions.append(
                                    (col, group, 'include')
                                )
                        condition_variations.append(group_conditions)
            
            # Generate all products of condition variations
            for condition_set in product(*condition_variations):
                # Apply all conditions in this set
                filtered_df = df.copy()
                applied_conditions = {}
                
                # Initialize all selected columns as blank
                for col in selected_columns:
                    applied_conditions[col] = ""
                
                # Apply each condition
                valid_filter = True
                for condition_item in condition_set:
                    # Handle OR logic conditions (list of conditions)
                    if isinstance(condition_item, list) and len(condition_item) > 0 and isinstance(condition_item[0], tuple):
                        # This is an OR condition group
                        col = condition_item[0][0]  # Get column from first condition
                        
                        if pd.api.types.is_numeric_dtype(df[col]):
                            # Handle multiple conditions with OR logic
                            or_mask = pd.Series([False] * len(filtered_df), index=filtered_df.index)
                            condition_descriptions = []
                            
                            for sub_col, sub_value, sub_operator in condition_item:
                                if sub_operator == '>':
                                    or_mask |= (filtered_df[sub_col] > sub_value)
                                    condition_descriptions.append(f"{sub_col} > {sub_value:.2f}")
                                elif sub_operator == '<':
                                    or_mask |= (filtered_df[sub_col] < sub_value)
                                    condition_descriptions.append(f"{sub_col} < {sub_value:.2f}")
                                elif sub_operator == '>=':
                                    or_mask |= (filtered_df[sub_col] >= sub_value)
                                    condition_descriptions.append(f"{sub_col} >= {sub_value:.2f}")
                                elif sub_operator == '<=':
                                    or_mask |= (filtered_df[sub_col] <= sub_value)
                                    condition_descriptions.append(f"{sub_col} <= {sub_value:.2f}")
                            
                            filtered_df = filtered_df[or_mask]
                            applied_conditions[col] = f"({' OR '.join(condition_descriptions)})"
                        continue
                    
                    # Handle regular conditions (single tuple)
                    col, threshold_data, operator = condition_item
                    
                    if is_date_column(df, col):
                        if operator == 'single_range':
                            filtered_df = apply_date_filter(filtered_df, col, threshold_data)
                            applied_conditions[col] = generate_date_condition_description(col, threshold_data, operator)
                        elif operator == 'range':
                            # Apply range filtering
                            start_date = pd.to_datetime(threshold_data["start_date"])
                            end_date = pd.to_datetime(threshold_data["end_date"])
                            col_data = pd.to_datetime(filtered_df[col], errors='coerce')
                            mask = (col_data.dt.date >= start_date.date()) & (col_data.dt.date <= end_date.date())
                            filtered_df = filtered_df[mask]
                            applied_conditions[col] = generate_date_condition_description(col, threshold_data, operator)
                        elif operator in ['before', 'after', 'on']:
                            # Apply single date filtering
                            col_data = pd.to_datetime(filtered_df[col], errors='coerce')
                            target_date = pd.to_datetime(threshold_data)
                            
                            if operator == 'before':
                                mask = col_data.dt.date < target_date.date()
                            elif operator == 'after':
                                mask = col_data.dt.date > target_date.date()
                            elif operator == 'on':
                                mask = col_data.dt.date == target_date.date()
                                
                            filtered_df = filtered_df[mask]
                            applied_conditions[col] = generate_date_condition_description(col, threshold_data, operator)
                        elif operator in ['last_n_days', 'first_n_days']:
                            # Apply N days filtering
                            col_data = pd.to_datetime(filtered_df[col], errors='coerce')
                            cutoff_date = pd.to_datetime(threshold_data["cutoff_date"])
                            
                            if operator == 'last_n_days':
                                mask = col_data >= cutoff_date
                            elif operator == 'first_n_days':
                                mask = col_data <= cutoff_date
                                
                            filtered_df = filtered_df[mask]
                            applied_conditions[col] = generate_date_condition_description(col, threshold_data, operator)

                    elif pd.api.types.is_numeric_dtype(df[col]):
                        if operator == 'range':
                            start = threshold_data["start"]
                            end = threshold_data["end"]
                            range_id = threshold_data["range_id"]
                            total_ranges = threshold_data["total_ranges"]
                            
                            # Apply range condition: >= start and < end (except for last range which includes end)
                            if range_id == total_ranges:  # Last range
                                filtered_df = filtered_df[(filtered_df[col] >= start) & (filtered_df[col] <= end)]
                                applied_conditions[col] = f"{col}: [{start:.2f} to {end:.2f}]"
                            else:
                                filtered_df = filtered_df[(filtered_df[col] >= start) & (filtered_df[col] < end)]
                                applied_conditions[col] = f"{col}: [{start:.2f} to {end:.2f})"
                        elif isinstance(operator, list):
                            # This should not happen anymore as OR logic is handled above
                            pass
                        elif operator == '>=':
                            filtered_df = filtered_df[filtered_df[col] >= threshold_data]
                            applied_conditions[col] = f"{col} >= {threshold_data:.2f}"
                        elif operator == '<':
                            filtered_df = filtered_df[filtered_df[col] < threshold_data]
                            applied_conditions[col] = f"{col} < {threshold_data:.2f}"
                        elif operator == '>':
                            filtered_df = filtered_df[filtered_df[col] > threshold_data]
                            applied_conditions[col] = f"{col} > {threshold_data:.2f}"
                    else:
                        if operator == 'include' and threshold_data:  # Only if values selected
                            filtered_df = filtered_df[filtered_df[col].isin(threshold_data)]
                            # Format the values list nicely
                            if len(threshold_data) == 1:
                                applied_conditions[col] = f"{col} = {threshold_data[0]}"
                            elif len(threshold_data) <= 3:
                                applied_conditions[col] = f"{col} in [{', '.join(map(str, threshold_data))}]"
                            else:
                                applied_conditions[col] = f"{col} in [{', '.join(map(str, threshold_data[:3]))}...] ({len(threshold_data)} values)"
                        elif not threshold_data:
                            valid_filter = False
                            break
                
                # Calculate result if filter is valid and data remains
                if valid_filter and not filtered_df.empty:
                    # Check minimum matching rows threshold
                    matching_rows = len(filtered_df)
                    if matching_rows < min_matching_rows:
                        continue  # Skip this combination as it doesn't meet minimum threshold
                    
                    # Create result row with condition columns first
                    result_row = applied_conditions.copy()
                    
                    # Add matching rows count
                    result_row['Matching_Rows'] = matching_rows
                    
                    # Calculate statistics for selected result columns
                    for result_col in result_columns:
                        if result_col in filtered_df.columns:
                            col_data = filtered_df[result_col].dropna()
                            
                            if not col_data.empty:
                                # Calculate mean
                                mean_value = col_data.mean()
                                if not pd.isna(mean_value):
                                    result_row[f'{result_col}_Mean'] = round(mean_value, 4)
                                
                                # Calculate max run
                                max_run = calculate_max_run(col_data)
                                result_row[f'{result_col}_Max_Run'] = max_run

                                # Calculate sum
                                sum_value = col_data.sum()
                                if not pd.isna(sum_value):
                                    result_row[f'{result_col}_Sum'] = round(sum_value, 4)
                                
                                # Calculate count
                                result_row[f'{result_col}_Count'] = len(col_data)
                                
                                # Calculate standard deviation
                                std_value = col_data.std()
                                if not pd.isna(std_value):
                                    result_row[f'{result_col}_Std_Dev'] = round(std_value, 4)
                                
                                # Calculate median
                                median_value = col_data.median()
                                if not pd.isna(median_value):
                                    result_row[f'{result_col}_Median'] = round(median_value, 4)
                                
                                # Calculate min and max
                                result_row[f'{result_col}_Min'] = round(col_data.min(), 4)
                                result_row[f'{result_col}_Max'] = round(col_data.max(), 4)
                    
                    # Add actual IDs (first 20 if more than 20)
                    ids = filtered_df[id_column].astype(str).tolist()
                    if len(ids) > 20:
                        ids = ids[:20]
                        result_row['IDs'] = ', '.join(ids) + f" ... ({len(filtered_df) - 20} more)"
                    else:
                        result_row['IDs'] = ', '.join(ids)
                    
                    results.append(result_row)
    
    return pd.DataFrame(results)

def apply_single_condition(df, column, threshold_config, operator):
    """Apply a single condition to the dataframe"""
    if is_date_column(df, column):
        return apply_date_filter(df, column, threshold_config)
    elif pd.api.types.is_numeric_dtype(df[column]):
        if operator == 'range':
            start = threshold_config["start"]
            end = threshold_config["end"]
            range_id = threshold_config["range_id"]
            total_ranges = threshold_config.get("total_ranges", 1)
            # For last range, include the end value
            if range_id == total_ranges:
                return df[(df[column] >= start) & (df[column] <= end)]
            else:
                return df[(df[column] >= start) & (df[column] < end)]
        elif operator == '>':
            return df[df[column] > threshold_config]
        elif operator == '<':
            return df[df[column] < threshold_config]
        elif operator == '>=':
            return df[df[column] >= threshold_config]
        elif operator == '<=':
            return df[df[column] <= threshold_config]
    else:
        if operator == 'include':
            return df[df[column].isin(threshold_config)]
        elif operator == 'exclude':
            return df[~df[column].isin(threshold_config)]
    
    return df

