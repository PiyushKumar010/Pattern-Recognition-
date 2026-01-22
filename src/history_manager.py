"""
History Manager - Professional Analysis History System
Handles dataset tracking, analysis history, and config-based caching
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.db import execute_query, get_db_cursor


def generate_config_hash(config: Dict) -> str:
    """
    Generate SHA256 hash of config for caching.
    Same config = same hash = can reuse cached results.
    
    Args:
        config: Analysis configuration dictionary
    
    Returns:
        SHA256 hash string
    """
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()


def generate_file_hash(file_content: bytes) -> str:
    """
    Generate SHA256 hash of file content.
    
    Args:
        file_content: Raw file bytes
    
    Returns:
        SHA256 hash string
    """
    return hashlib.sha256(file_content).hexdigest()


def save_dataset(original_filename: str, table_name: str, file_hash: str, 
                 file_size_bytes: int, rows_count: int, columns_count: int) -> Optional[int]:
    """
    Save dataset metadata to database.
    
    Args:
        original_filename: Original uploaded filename
        table_name: Database table name
        file_hash: SHA256 hash of file
        file_size_bytes: File size in bytes
        rows_count: Number of rows
        columns_count: Number of columns
    
    Returns:
        dataset_id if successful, None otherwise
    """
    try:
        with get_db_cursor() as cursor:
            # Check if dataset already exists
            cursor.execute(
                "SELECT id FROM datasets WHERE table_name = %s",
                (table_name,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update last_accessed_at
                cursor.execute(
                    "UPDATE datasets SET last_accessed_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (existing[0],)
                )
                return existing[0]
            
            # Insert new dataset
            cursor.execute(
                """INSERT INTO datasets 
                   (original_filename, table_name, file_hash, file_size_bytes, rows_count, columns_count)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (original_filename, table_name, file_hash, file_size_bytes, rows_count, columns_count)
            )
            dataset_id = cursor.fetchone()[0]
            return dataset_id
    except Exception as e:
        print(f"Error saving dataset: {e}")
        return None


def get_dataset_by_table_name(table_name: str) -> Optional[Dict]:
    """
    Get dataset metadata by table name.
    
    Args:
        table_name: Database table name
    
    Returns:
        Dataset dictionary or None
    """
    try:
        from psycopg2.extras import RealDictCursor
        with get_db_cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM datasets WHERE table_name = %s",
                (table_name,)
            )
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"Error fetching dataset: {e}")
        return None


def find_cached_analysis(dataset_id: int, config_hash: str) -> Optional[Dict]:
    """
    Check if analysis with same config already exists (for caching).
    
    Args:
        dataset_id: Dataset ID
        config_hash: Config hash
    
    Returns:
        Analysis result if cached, None otherwise
    """
    try:
        from psycopg2.extras import RealDictCursor
        with get_db_cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT * FROM analysis_history 
                   WHERE dataset_id = %s AND config_hash = %s AND status = 'completed'
                   ORDER BY created_at DESC LIMIT 1""",
                (dataset_id, config_hash)
            )
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"Error checking cache: {e}")
        return None


def save_analysis(dataset_id: int, config: Dict, status: str = 'pending',
                  execution_time_ms: Optional[int] = None,
                  result_preview: Optional[Dict] = None,
                  result_row_count: Optional[int] = None,
                  error_message: Optional[str] = None) -> Optional[int]:
    """
    Save analysis run to history.
    
    Args:
        dataset_id: Dataset ID
        config: Analysis configuration
        status: 'pending', 'completed', or 'failed'
        execution_time_ms: Execution time in milliseconds
        result_preview: Preview of results (dict/list, max 100 rows)
        result_row_count: Total number of result rows
        error_message: Error message if failed
    
    Returns:
        analysis_id if successful, None otherwise
    """
    try:
        config_hash = generate_config_hash(config)
        config_json = json.dumps(config)
        result_preview_json = json.dumps(result_preview) if result_preview else None
        
        with get_db_cursor() as cursor:
            cursor.execute(
                """INSERT INTO analysis_history 
                   (dataset_id, config_json, config_hash, status, execution_time_ms, 
                    result_preview, result_row_count, error_message, completed_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (dataset_id, config_json, config_hash, status, execution_time_ms,
                 result_preview_json, result_row_count, error_message,
                 datetime.now() if status == 'completed' else None)
            )
            analysis_id = cursor.fetchone()[0]
            return analysis_id
    except Exception as e:
        print(f"Error saving analysis: {e}")
        return None


def get_analysis_history(limit: int = 50, offset: int = 0) -> List[Dict]:
    """
    Get analysis history with dataset info (paginated).
    
    Args:
        limit: Number of records to return
        offset: Offset for pagination
    
    Returns:
        List of analysis records with dataset info
    """
    try:
        from psycopg2.extras import RealDictCursor
        with get_db_cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT 
                       ah.id,
                       ah.dataset_id,
                       ah.config_json,
                       ah.config_hash,
                       ah.status,
                       ah.execution_time_ms,
                       ah.result_row_count,
                       ah.created_at,
                       ah.completed_at,
                       d.original_filename,
                       d.table_name,
                       d.rows_count as dataset_rows
                   FROM analysis_history ah
                   JOIN datasets d ON ah.dataset_id = d.id
                   ORDER BY ah.created_at DESC
                   LIMIT %s OFFSET %s""",
                (limit, offset)
            )
            results = cursor.fetchall()
            return results
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []


def get_analysis_by_id(analysis_id: int) -> Optional[Dict]:
    """
    Get specific analysis by ID with full details.
    
    Args:
        analysis_id: Analysis ID
    
    Returns:
        Analysis record or None
    """
    try:
        from psycopg2.extras import RealDictCursor
        with get_db_cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT 
                       ah.*,
                       d.original_filename,
                       d.table_name,
                       d.rows_count as dataset_rows,
                       d.columns_count
                   FROM analysis_history ah
                   JOIN datasets d ON ah.dataset_id = d.id
                   WHERE ah.id = %s""",
                (analysis_id,)
            )
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"Error fetching analysis: {e}")
        return None


def delete_analysis(analysis_id: int) -> bool:
    """
    Delete analysis from history.
    
    Args:
        analysis_id: Analysis ID
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM analysis_history WHERE id = %s", (analysis_id,))
            return True
    except Exception as e:
        print(f"Error deleting analysis: {e}")
        return False


def clear_all_history() -> bool:
    """
    Delete all analysis history records.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM analysis_history")
            return True
    except Exception as e:
        print(f"Error clearing history: {e}")
        return False


def get_history_stats() -> Dict:
    """
    Get statistics about analysis history.
    
    Returns:
        Dictionary with stats
    """
    try:
        from psycopg2.extras import RealDictCursor
        with get_db_cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT 
                       COUNT(*) as total_analyses,
                       COUNT(DISTINCT dataset_id) as total_datasets,
                       AVG(execution_time_ms) as avg_execution_time_ms,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count
                   FROM analysis_history"""
            )
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {}
