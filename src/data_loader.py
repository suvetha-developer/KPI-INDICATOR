"""
Data loader for Olist CSV files.
Loads CSV files into database with proper schema and data cleaning.
"""
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from src.database import DatabaseConnection

logger = logging.getLogger(__name__)


class DataLoader:
    """Loads Olist CSV files into database."""
    
    # Olist dataset table schemas
    SCHEMAS = {
        'olist_customers_dataset': """
            CREATE TABLE IF NOT EXISTS olist_customers_dataset (
                customer_id TEXT PRIMARY KEY,
                customer_unique_id TEXT,
                customer_zip_code_prefix TEXT,
                customer_city TEXT,
                customer_state TEXT
            )
        """,
        'olist_geolocation_dataset': """
            CREATE TABLE IF NOT EXISTS olist_geolocation_dataset (
                geolocation_zip_code_prefix TEXT,
                geolocation_lat REAL,
                geolocation_lng REAL,
                geolocation_city TEXT,
                geolocation_state TEXT
            )
        """,
        'olist_order_items_dataset': """
            CREATE TABLE IF NOT EXISTS olist_order_items_dataset (
                order_id TEXT,
                order_item_id INTEGER,
                product_id TEXT,
                seller_id TEXT,
                shipping_limit_date TEXT,
                price REAL,
                freight_value REAL,
                PRIMARY KEY (order_id, order_item_id),
                FOREIGN KEY (order_id) REFERENCES olist_orders_dataset(order_id),
                FOREIGN KEY (product_id) REFERENCES olist_products_dataset(product_id),
                FOREIGN KEY (seller_id) REFERENCES olist_sellers_dataset(seller_id)
            )
        """,
        'olist_order_payments_dataset': """
            CREATE TABLE IF NOT EXISTS olist_order_payments_dataset (
                order_id TEXT,
                payment_sequential INTEGER,
                payment_type TEXT,
                payment_installments INTEGER,
                payment_value REAL,
                PRIMARY KEY (order_id, payment_sequential),
                FOREIGN KEY (order_id) REFERENCES olist_orders_dataset(order_id)
            )
        """,
        'olist_order_reviews_dataset': """
            CREATE TABLE IF NOT EXISTS olist_order_reviews_dataset (
                review_id TEXT PRIMARY KEY,
                order_id TEXT,
                review_score INTEGER,
                review_comment_title TEXT,
                review_comment_message TEXT,
                review_creation_date TEXT,
                review_answer_timestamp TEXT,
                FOREIGN KEY (order_id) REFERENCES olist_orders_dataset(order_id)
            )
        """,
        'olist_orders_dataset': """
            CREATE TABLE IF NOT EXISTS olist_orders_dataset (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT,
                order_status TEXT,
                order_purchase_timestamp TEXT,
                order_approved_at TEXT,
                order_delivered_carrier_date TEXT,
                order_delivered_customer_date TEXT,
                order_estimated_delivery_date TEXT,
                FOREIGN KEY (customer_id) REFERENCES olist_customers_dataset(customer_id)
            )
        """,
        'olist_products_dataset': """
            CREATE TABLE IF NOT EXISTS olist_products_dataset (
                product_id TEXT PRIMARY KEY,
                product_category_name TEXT,
                product_name_lenght REAL,
                product_description_lenght REAL,
                product_photos_qty REAL,
                product_weight_g REAL,
                product_length_cm REAL,
                product_height_cm REAL,
                product_width_cm REAL
            )
        """,
        'olist_sellers_dataset': """
            CREATE TABLE IF NOT EXISTS olist_sellers_dataset (
                seller_id TEXT PRIMARY KEY,
                seller_zip_code_prefix TEXT,
                seller_city TEXT,
                seller_state TEXT
            )
        """,
        'product_category_name_translation': """
            CREATE TABLE IF NOT EXISTS product_category_name_translation (
                product_category_name TEXT PRIMARY KEY,
                product_category_name_english TEXT
            )
        """
    }
    
    def __init__(self, db: DatabaseConnection, data_dir: str = "data"):
        """
        Initialize data loader.
        
        Args:
            db: Database connection instance
            data_dir: Directory containing CSV files
        """
        self.db = db
        self.data_dir = Path(data_dir)
        
    def create_schema(self):
        """Create all database tables."""
        logger.info("Creating database schema...")
        
        # Create tables in dependency order
        order = [
            'olist_customers_dataset',
            'olist_sellers_dataset',
            'olist_products_dataset',
            'olist_geolocation_dataset',
            'product_category_name_translation',
            'olist_orders_dataset',
            'olist_order_items_dataset',
            'olist_order_payments_dataset',
            'olist_order_reviews_dataset'
        ]
        
        for table_name in order:
            if table_name in self.SCHEMAS:
                try:
                    self.db.execute_non_query(self.SCHEMAS[table_name])
                    logger.info(f"Created table: {table_name}")
                except Exception as e:
                    logger.warning(f"Table {table_name} may already exist: {str(e)}")
        
        # Create indexes for performance
        self._create_indexes()
        logger.info("Schema creation complete")
    
    def _create_indexes(self):
        """Create indexes on frequently queried columns."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_orders_customer ON olist_orders_dataset(customer_id)",
            "CREATE INDEX IF NOT EXISTS idx_orders_status ON olist_orders_dataset(order_status)",
            "CREATE INDEX IF NOT EXISTS idx_orders_purchase_date ON olist_orders_dataset(order_purchase_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_order_items_order ON olist_order_items_dataset(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_order_payments_order ON olist_order_payments_dataset(order_id)",
            "CREATE INDEX IF NOT EXISTS idx_order_reviews_order ON olist_order_reviews_dataset(order_id)",
        ]
        
        for index_sql in indexes:
            try:
                self.db.execute_non_query(index_sql)
            except Exception as e:
                logger.warning(f"Index creation warning: {str(e)}")
    
    def load_csv_file(self, csv_path: Path, table_name: str, chunk_size: int = 10000) -> int:
        """
        Load a single CSV file into database table.
        
        Args:
            csv_path: Path to CSV file
            table_name: Target table name
            chunk_size: Number of rows to process at a time
            
        Returns:
            Number of rows loaded
        """
        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            return 0
        
        logger.info(f"Loading {csv_path.name} into {table_name}...")
        
        try:
            # Temporarily disable foreign key constraints for SQLite
            if self.db.db_type == 'sqlite':
                self.db.execute_non_query("PRAGMA foreign_keys = OFF")
            
            # Read CSV in chunks to handle large files
            total_rows = 0
            chunk_iter = pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False)
            
            for chunk in chunk_iter:
                # Clean data
                chunk = self._clean_dataframe(chunk, table_name)
                
                # Convert to list of dictionaries for insertion
                records = chunk.to_dict('records')
                
                if not records:
                    continue
                
                # Build INSERT query
                columns = list(records[0].keys())
                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join(columns)
                
                insert_query = f"""
                    INSERT OR REPLACE INTO {table_name} ({columns_str})
                    VALUES ({placeholders})
                """
                
                # Insert records
                cursor = self.db.connection.cursor()
                for record in records:
                    values = [record.get(col) for col in columns]
                    cursor.execute(insert_query, values)
                
                self.db.connection.commit()
                total_rows += len(records)
                logger.info(f"  Loaded {total_rows} rows...")
            
            # Re-enable foreign key constraints
            if self.db.db_type == 'sqlite':
                self.db.execute_non_query("PRAGMA foreign_keys = ON")
            
            logger.info(f"Successfully loaded {total_rows} rows into {table_name}")
            return total_rows
            
        except Exception as e:
            # Re-enable foreign key constraints even on error
            if self.db.db_type == 'sqlite':
                try:
                    self.db.execute_non_query("PRAGMA foreign_keys = ON")
                except:
                    pass
            logger.error(f"Error loading {csv_path.name}: {str(e)}")
            raise
    
    def _clean_dataframe(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """
        Clean dataframe before loading.
        
        Args:
            df: DataFrame to clean
            table_name: Table name for context-specific cleaning
            
        Returns:
            Cleaned DataFrame
        """
        # Remove leading/trailing whitespace from string columns
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()
                # Replace 'nan' strings with None
                df[col] = df[col].replace(['nan', 'None', ''], None)
        
        # Handle date columns - keep as text for SQLite compatibility
        # SQLite will store dates as TEXT, which is fine for our queries
        
        return df
    
    def load_all_csv_files(self) -> Dict[str, int]:
        """
        Load all Olist CSV files from data directory.
        
        Returns:
            Dictionary mapping table names to row counts
        """
        if not self.data_dir.exists():
            logger.error(f"Data directory not found: {self.data_dir}")
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        
        # Map CSV file names to table names
        csv_to_table = {
            'olist_customers_dataset.csv': 'olist_customers_dataset',
            'olist_geolocation_dataset.csv': 'olist_geolocation_dataset',
            'olist_order_items_dataset.csv': 'olist_order_items_dataset',
            'olist_order_payments_dataset.csv': 'olist_order_payments_dataset',
            'olist_order_reviews_dataset.csv': 'olist_order_reviews_dataset',
            'olist_orders_dataset.csv': 'olist_orders_dataset',
            'olist_products_dataset.csv': 'olist_products_dataset',
            'olist_sellers_dataset.csv': 'olist_sellers_dataset',
            'product_category_name_translation.csv': 'product_category_name_translation'
        }
        
        results = {}
        
        # Create schema first
        self.create_schema()
        
        # Load each CSV file
        for csv_file, table_name in csv_to_table.items():
            csv_path = self.data_dir / csv_file
            
            if csv_path.exists():
                try:
                    row_count = self.load_csv_file(csv_path, table_name)
                    results[table_name] = row_count
                except Exception as e:
                    logger.error(f"Failed to load {csv_file}: {str(e)}")
                    results[table_name] = 0
            else:
                logger.warning(f"CSV file not found: {csv_file}")
                results[table_name] = 0
        
        return results
    
    def verify_data_loaded(self) -> Dict[str, int]:
        """
        Verify data was loaded correctly by counting rows in each table.
        
        Returns:
            Dictionary mapping table names to row counts
        """
        results = {}
        
        for table_name in self.SCHEMAS.keys():
            try:
                query = f"SELECT COUNT(*) as count FROM {table_name}"
                result = self.db.execute_query(query)
                count = result[0]['count'] if result else 0
                results[table_name] = count
                logger.info(f"{table_name}: {count} rows")
            except Exception as e:
                logger.warning(f"Could not verify {table_name}: {str(e)}")
                results[table_name] = 0
        
        return results

