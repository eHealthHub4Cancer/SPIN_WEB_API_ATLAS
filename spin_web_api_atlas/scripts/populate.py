#!/usr/bin/env python3
"""
Simple OMOP CDM Source Table Loader
Loads source configuration into the database source table
"""

import os
import sys
import logging
from contextlib import contextmanager
import requests

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup"""
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'synthea_omop'),
            user=os.getenv('DB_USER', 'username'),
            password=os.getenv('DB_PASSWORD', 'password')
        )
        yield conn
    except Exception as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def source_exists(cursor, source_key, schema):
    """Check if source already exists"""
    cursor.execute(f"SELECT 1 FROM {schema}.source WHERE source_key = %s", (source_key,))
    return cursor.fetchone() is not None


def create_source(cursor, source_config, schema):
    """Create source entry"""
    cursor.execute(f"""
        INSERT INTO {schema}.source (source_name, source_key, source_connection, source_dialect)
        VALUES (%s, %s, %s, %s)
        RETURNING source_id
    """, (
        source_config['name'],
        source_config['key'],
        source_config['connection'],
        source_config['dialect']
    ))
    
    source_id = cursor.fetchone()['source_id']
    logger.info(f"Created source with ID: {source_id}")
    return source_id


def create_source_daimons(cursor, source_id, source_config, schema):
    """Create source daimon entries"""
    daimons = [
        (source_id, 0, source_config['cdm_schema'], 0),      # CDM
        (source_id, 1, source_config['vocab_schema'], 1),    # Vocabulary
        (source_id, 2, source_config['results_schema'], 1),   # Results
        (source_id, 5, source_config['temp_schema'], 0)  # temp schema    # Temp
    ]
    
    cursor.executemany(f"""
        INSERT INTO {schema}.source_daimon (source_id, daimon_type, table_qualifier, priority)
        VALUES (%s, %s, %s, %s)
    """, daimons)
    
    logger.info("Created source daimons")


def load_source_table():
    """Load source configuration into database"""
    source_config = {
        'name': os.getenv("SOURCE_NAME", "AML Practice"),
        'key': os.getenv("SOURCE_KEY", "MY_CDM"),
        'connection': os.getenv("SOURCE_CONNECTION", "jdbc:postgresql://postgres-db:5432/aml_report?user=broadsea_user&password=broadsea_password"),
        'dialect': os.getenv("SOURCE_DIALECT", "postgresql"),
        'cdm_schema': os.getenv("CDM_SCHEMA", "cdm_1"),
        'results_schema': os.getenv("RESULTS_SCHEMA", "result_1"),
        'vocab_schema': os.getenv("VOCAB_SCHEMA", "cdm"),
        'temp_schema': os.getenv("TEMP_SCHEMA", "temp_schema_1")
    }
    
    # Get schema from environment variable
    schema = os.getenv("WEBAPI_DATASOURCE_OHDSI_SCHEMA", "new_one")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                if source_exists(cursor, source_config['key'], schema):
                    logger.info(f"Source '{source_config['key']}' already exists. Skipping.")
                    return True
                
                logger.info(f"Creating source: {source_config['name']} in schema: {schema}")
                source_id = create_source(cursor, source_config, schema)
                create_source_daimons(cursor, source_id, source_config, schema)
                
                conn.commit()
                logger.info("Source table loaded successfully")
                return True
                
    except Exception as e:
        logger.error(f"Failed to load source table: {e}")
        return False


def main():
    """Main function"""
    logger.info("Starting source table loader")
    
    if load_source_table():
        logger.info("Source table loading completed successfully")
    else:
        logger.error("Source table loading failed")
        sys.exit(1)

def refresh_source_table():
    """Refresh source table"""
    logger.info("Refreshing source table")
    response = requests.get("http://ohdsi-webapi-3:8080/WebAPI/source/refresh", timeout=60)
    logger.info(f"Status: {response.status_code} | Response: {response.text}")
    return response.status_code == 200

if __name__ == "__main__":
    main()
    if not refresh_source_table():
        logger.error("Source table refresh failed")