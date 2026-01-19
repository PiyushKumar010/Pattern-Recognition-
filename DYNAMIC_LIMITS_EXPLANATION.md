# Dynamic Combination Limits - Implementation Guide

## Overview
This project now uses **dynamic combination limits** instead of hard-coded limits to prevent computational overload while maximizing flexibility.

## What Changed?

### Previous Behavior
- Hard-coded maximum of **20** ranges/conditions for all filtering options
- No awareness of total computational impact
- Could easily exceed memory/performance limits

### New Behavior
- **Dynamic calculation** based on total estimated combinations
- Maximum total combinations: **100,000** (configurable in `config.py`)
- Automatically adjusts allowed ranges based on selected columns
- Visual feedback showing estimated combinations

## How It Works

### 1. Maximum Combinations Formula
```
Max Combinations = 100,000 (default)
Max Ranges Per Column = Max Combinations ÷ (estimated combinations from other columns)
```

### 2. Examples

#### Example 1: Single Column
- Selected columns: 1
- Other columns estimate: 1
- **Max ranges allowed: 100,000** (capped at 1,000 for practicality)

#### Example 2: Two Columns
- Selected columns: 2
- Other columns estimate: 3 conditions
- **Max ranges allowed: 33,333** for current column (capped at 1,000)

#### Example 3: Five Columns
- Selected columns: 5
- Other columns estimate: 3^4 = 81
- **Max ranges allowed: 1,234** for current column

#### Example 4: Many Columns
- Selected columns: 10
- Other columns estimate: 3^9 = 19,683
- **Max ranges allowed: 5** for current column

## Updated Features

### All filtering options now use dynamic limits:

1. **Multiple Date Ranges** (WindEquipmentChangeDate)
   - Previously: max 20 ranges
   - Now: dynamically calculated

2. **Before Dates** (multiple)
   - Previously: max 20 dates
   - Now: dynamically calculated

3. **After Dates** (multiple)
   - Previously: max 20 dates
   - Now: dynamically calculated

4. **On Dates** (multiple)
   - Previously: max 20 dates
   - Now: dynamically calculated

5. **Multiple Conditions (OR Logic)**
   - Previously: max 20 conditions
   - Now: dynamically calculated

6. **Range Divisions** (numeric columns)
   - Previously: max 20 divisions
   - Now: dynamically calculated

## Visual Feedback

The UI now displays:

### ✓ Safe (Green)
```
✓ Estimated combinations: 243 - Within safe limits
```

### ⚠️ Warning (Yellow)
```
⚠️ Estimated combinations: 75,000 - Approaching limit of 100,000. Analysis may be slow.
```

### ⚠️ Error (Red)
```
⚠️ Estimated combinations: 150,000 - Exceeds limit of 100,000! 
Please reduce the number of ranges/conditions.
```

## Configuration

### Adjusting the Maximum Limit

Edit `config.py`:

```python
# Increase for more powerful systems
MAX_TOTAL_COMBINATIONS = 500000  # Allow 500K combinations

# Decrease for resource-constrained systems
MAX_TOTAL_COMBINATIONS = 50000   # Limit to 50K combinations
```

### Understanding the Trade-offs

| Limit | Pro | Con |
|-------|-----|-----|
| 10,000 | Very fast | Limited flexibility |
| 100,000 | Balanced (default) | Moderate speed |
| 1,000,000 | Maximum flexibility | Can be very slow |

## Technical Details

### Function: `calculate_max_ranges()`

**Location:** `config.py`

**Parameters:**
- `selected_columns_count`: Number of columns selected for analysis
- `current_column_ranges`: Dictionary of existing range counts (optional)

**Returns:**
- Integer between 2 and 1,000 representing max allowed ranges

**Algorithm:**
1. Calculate estimated product of other columns (default: 3 conditions each)
2. Divide MAX_TOTAL_COMBINATIONS by this product
3. Apply bounds (minimum: 2, maximum: 1,000)
4. Return result

### Import Usage

In `app.py`:
```python
from config import MAX_TOTAL_COMBINATIONS, calculate_max_ranges

# Calculate dynamic limit
max_ranges = calculate_max_ranges(len(selected_columns))

# Use in UI
st.number_input(
    "Number of ranges",
    min_value=1,
    max_value=max_ranges,  # Dynamic limit
    help=f"Maximum {max_ranges} ranges allowed"
)
```

## Benefits

1. **Prevents System Overload**: Automatically prevents computationally infeasible operations
2. **Maximizes Flexibility**: Allows more ranges when fewer columns are selected
3. **User Awareness**: Shows real-time combination estimates
4. **Configurable**: Easy to adjust for different system capabilities
5. **Scalable**: Works efficiently regardless of column count

## Performance Impact

### Before
- Could set 20 ranges × 10 columns = 20^10 = 10,240,000,000,000 combinations ❌
- System would freeze/crash

### After
- Maximum 100,000 combinations enforced ✓
- System remains responsive
- Analysis completes in reasonable time

## Troubleshooting

### "Estimated combinations exceeds limit" Error

**Solution 1:** Reduce the number of ranges/conditions per column

**Solution 2:** Analyze fewer columns at once

**Solution 3:** Increase `MAX_TOTAL_COMBINATIONS` in `config.py`

### "Max ranges allowed is too low"

This happens when many columns are selected.

**Solution:** 
- Analyze columns in batches
- Or increase `MAX_TOTAL_COMBINATIONS` if system can handle it

## Future Enhancements

Possible improvements:
1. **Adaptive limits** based on system memory
2. **Parallel processing** for large combination sets
3. **Sampling mode** for very large datasets
4. **Progress bars** for long-running analyses

---

**Last Updated:** January 19, 2026
**Version:** 2.0
