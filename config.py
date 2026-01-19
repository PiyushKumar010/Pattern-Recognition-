# filepath: /data-analysis-tool/data-analysis-tool/config.py
DEFAULT_THRESHOLD = 0.0
SUPPORTED_FILE_TYPES = ['xlsx', 'xls']
ANALYSIS_OPTIONS = ['mean', 'median', 'mode']
RESULTS_SHEET_NAME = 'Analysis Results'
MAX_ROWS_DISPLAY = 200

# Maximum total combinations optimized for fast execution
# This is the product of all condition variations across all selected columns
# Set to 10,000 for optimal performance - analysis completes in < 30 seconds
MAX_TOTAL_COMBINATIONS = 10000

def calculate_max_ranges(selected_columns_count: int, current_column_ranges: dict = None) -> int:
    """
    Calculate the maximum number of ranges/conditions allowed for a column
    based on the maximum total combinations limit.
    
    Args:
        selected_columns_count: Total number of columns selected for analysis
        current_column_ranges: Dict mapping column names to their current range counts
    
    Returns:
        Maximum number of ranges allowed for the current column
    """
    if selected_columns_count == 0:
        return 100  # Default high value if no columns selected
    
    # Calculate current product of existing column ranges
    if current_column_ranges:
        current_product = 1
        for count in current_column_ranges.values():
            current_product *= max(count, 2)  # Assume at least 2 conditions per column
    else:
        # Conservative estimate: assume other columns have average of 3 conditions each
        other_columns = max(0, selected_columns_count - 1)
        current_product = 3 ** other_columns if other_columns > 0 else 1
    
    # Calculate max ranges for this column
    if current_product > 0:
        max_ranges = int(MAX_TOTAL_COMBINATIONS / current_product)
        # Apply reasonable bounds
        return max(2, min(max_ranges, 1000))  # Between 2 and 1000
    
    return 100  # Default fallback
