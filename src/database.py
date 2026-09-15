"""
Database connection handler for multiple database types.
Supports SQLite (default for Olist), PostgreSQL, MySQL, and SQL Server.
"""
import logging
import sqlite3
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Handles database connections for SQLite (default), PostgreSQL, MySQL, SQL Server."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize database connection.
        
        Args:
            config: Database configuration dictionary
                For SQLite: {'type': 'sqlite', 'database': 'path/to/database.db'}
                For PostgreSQL: {'type': 'postgresql', 'host': '...', 'port': 5432, ...}
        """
        self.config = config
        self.connection = None
        self.db_type = config.get('type', 'sqlite').lower()
        
    def connect(self):
        """Establish database connection."""
        try:
            if self.db_type == 'sqlite':
                db_path = self.config.get('database', 'data/olist.db')
                # Create directory if it doesn't exist
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                self.connection = sqlite3.connect(db_path, check_same_thread=False)
                # Enable foreign keys
                self.connection.execute("PRAGMA foreign_keys = ON")
                logger.info(f"Connected to SQLite database: {db_path}")
                
            elif self.db_type == 'postgresql':
                import psycopg2
                self.connection = psycopg2.connect(
                    host=self.config['host'],
                    port=self.config.get('port', 5432),
                    database=self.config['database'],
                    user=self.config['user'],
                    password=self.config['password']
                )
                logger.info(f"Connected to PostgreSQL database")
                
            elif self.db_type == 'mysql':
                import pymysql
                self.connection = pymysql.connect(
                    host=self.config['host'],
                    port=self.config.get('port', 3306),
                    database=self.config['database'],
                    user=self.config['user'],
                    password=self.config['password']
                )
                logger.info(f"Connected to MySQL database")
                
            elif self.db_type in ['sqlserver', 'mssql']:
                import pyodbc
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={self.config['host']};"
                    f"DATABASE={self.config['database']};"
                    f"UID={self.config['user']};"
                    f"PWD={self.config['password']}"
                )
                self.connection = pyodbc.connect(conn_str)
                logger.info(f"Connected to SQL Server database")
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")
            
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            raise
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results.
        
        Args:
            query: SQL query string
            params: Optional query parameters (for parameterized queries)
            
        Returns:
            List of dictionaries with query results
        """
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            
            # SQLite uses ? for parameters, others use %s or named parameters
            if params and self.db_type == 'sqlite':
                # Convert dict params to tuple if needed
                if isinstance(params, dict):
                    # For SQLite with named parameters, use :param_name syntax
                    cursor.execute(query, params)
                else:
                    cursor.execute(query, params)
            elif params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Get column names
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
            else:
                columns = []
            
            # Fetch all results
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            results = [dict(zip(columns, row)) for row in rows]
            
            cursor.close()
            return results
            
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            logger.error(f"Query: {query[:200]}...")  # Log first 200 chars
            raise
    
    def execute_non_query(self, query: str, params: Optional[Dict] = None):
        """
        Execute a non-query SQL statement (INSERT, UPDATE, DELETE, CREATE, etc.).
        
        Args:
            query: SQL query string
            params: Optional query parameters
        """
        if not self.connection:
            self.connect()
        
        try:
            cursor = self.connection.cursor()
            
            if params and self.db_type == 'sqlite':
                if isinstance(params, dict):
                    cursor.execute(query, params)
                else:
                    cursor.execute(query, params)
            elif params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            self.connection.commit()
            cursor.close()
            
        except Exception as e:
            logger.error(f"Non-query execution failed: {str(e)}")
            logger.error(f"Query: {query[:200]}...")
            self.connection.rollback()
            raise
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

