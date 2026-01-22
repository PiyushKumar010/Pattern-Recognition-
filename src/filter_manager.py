import pandas as pd


def generate_sql_condition(column, threshold_config, column_type='numeric'):
    """
    Generate SQL WHERE clause condition for a single column based on threshold configuration.
    
    Args:
        column (str): Column name
        threshold_config (dict): Threshold configuration
        column_type (str): 'numeric', 'date', or 'categorical'
    
    Returns:
        list: List of SQL condition strings
    """
    conditions = []
    
    if column_type == 'date':
        if threshold_config["type"] == "single_range":
            start = threshold_config["start_date"]
            end = threshold_config["end_date"]
            conditions.append(f"\"{column}\"::date BETWEEN '{start}' AND '{end}'")
            
        elif threshold_config["type"] == "multiple_ranges":
            for range_config in threshold_config["ranges"]:
                start = range_config["start_date"]
                end = range_config["end_date"]
                conditions.append(f"\"{column}\"::date BETWEEN '{start}' AND '{end}'")
                
        elif threshold_config["type"] == "multiple_before":
            for date in threshold_config["dates"]:
                conditions.append(f"\"{column}\"::date < '{date}'")
                
        elif threshold_config["type"] == "multiple_after":
            for date in threshold_config["dates"]:
                conditions.append(f"\"{column}\"::date > '{date}'")
                
        elif threshold_config["type"] == "multiple_on":
            for date in threshold_config["dates"]:
                conditions.append(f"\"{column}\"::date = '{date}'")
                
        elif threshold_config["type"] == "multiple_last_n_days":
            for config in threshold_config["configs"]:
                cutoff = config["cutoff_date"]
                conditions.append(f"\"{column}\"::date >= '{cutoff}'")
                
        elif threshold_config["type"] == "multiple_first_n_days":
            for config in threshold_config["configs"]:
                cutoff = config["cutoff_date"]
                conditions.append(f"\"{column}\"::date <= '{cutoff}'")
                
    elif column_type == 'numeric':
        if threshold_config["type"] == "range":
            for i, (start, end) in enumerate(threshold_config["ranges"], 1):
                if i == len(threshold_config["ranges"]):  # Last range includes end
                    conditions.append(f"\"{column}\" >= {start} AND \"{column}\" <= {end}")
                else:
                    conditions.append(f"\"{column}\" >= {start} AND \"{column}\" < {end}")
                    
        elif threshold_config["type"] == "multiple_conditions_or":
            # Individual conditions
            for condition in threshold_config["conditions"]:
                op = condition["operator"]
                val = condition["value"]
                conditions.append(f"\"{column}\" {op} {val}")
                
            # Combined OR condition
            or_parts = [f"\"{column}\" {c['operator']} {c['value']}" for c in threshold_config["conditions"]]
            conditions.append(f"({' OR '.join(or_parts)})")
            
        else:  # mean, median, custom
            value = threshold_config["value"]
            conditions.append(f"\"{column}\" >= {value}")
            conditions.append(f"\"{column}\" < {value}")
            
    elif column_type == 'categorical':
        if threshold_config["type"] == "categorical" and threshold_config.get("value_groups"):
            for group in threshold_config["value_groups"]:
                if group:
                    # Escape single quotes in values
                    escaped_values = [str(v).replace("'", "''") for v in group]
                    values_str = "', '".join(escaped_values)
                    conditions.append(f"\"{column}\" IN ('{values_str}')")
    
    return conditions


def build_sql_query(table_name, selected_columns, thresholds, column_types, result_columns=None, id_column=None):
    """
    Build a complete SQL query with WHERE conditions based on thresholds.
    
    Args:
        table_name (str): Name of the database table
        selected_columns (list): Columns to filter on
        thresholds (dict): Threshold configurations for each column
        column_types (dict): Data types for each column
        result_columns (list): Columns to aggregate (optional)
        id_column (str): ID column name (optional)
    
    Returns:
        str: SQL query string
    """
    # Build SELECT clause
    if result_columns:
        select_parts = []
        for col in result_columns:
            select_parts.extend([
                f"AVG(\"{col}\") as {col}_mean",
                f"SUM(\"{col}\") as {col}_sum",
                f"COUNT(\"{col}\") as {col}_count",
                f"STDDEV(\"{col}\") as {col}_stddev",
                f"MIN(\"{col}\") as {col}_min",
                f"MAX(\"{col}\") as {col}_max"
            ])
        select_clause = ", ".join(select_parts)
    else:
        select_clause = "*"
    
    # Build WHERE clause
    where_conditions = []
    for col in selected_columns:
        if col in thresholds:
            col_type = column_types.get(col, 'numeric')
            conditions = generate_sql_condition(col, thresholds[col], col_type)
            if conditions:
                # For multiple conditions, combine with OR
                if len(conditions) > 1:
                    where_conditions.append(f"({' OR '.join(conditions)})")
                else:
                    where_conditions.extend(conditions)
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    # Build complete query
    query = f"SELECT {select_clause} FROM {table_name} WHERE {where_clause}"
    
    return query


def apply_filters(df, selected_columns, thresholds):
    """
    Legacy function - applies filters using pandas (kept for backward compatibility).
    Use generate_sql_condition and build_sql_query for database-driven filtering.
    """
    filtered_df = df.copy()
    
    for col in selected_columns:
        if col in filtered_df.columns:
            threshold = thresholds.get(col)
            if pd.api.types.is_numeric_dtype(filtered_df[col]):
                filtered_df = filtered_df[filtered_df[col] > threshold]
            else:
                mode_value = filtered_df[col].mode().iloc[0]
                filtered_df = filtered_df[filtered_df[col] == mode_value]

    return filtered_df


def get_remaining_columns(original_df, filtered_df):
    """Get columns that are not in the filtered dataframe."""
    remaining_columns = original_df.columns.difference(filtered_df.columns)
    return remaining_columns.tolist()