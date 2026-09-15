"""
Database setup script for Olist dataset.
Loads all CSV files from data directory into SQLite database.
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseConnection
from src.data_loader import DataLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Main setup function."""
    logger.info("=" * 60)
    logger.info("Olist Dataset Database Setup")
    logger.info("=" * 60)
    
    # Database configuration (SQLite for simplicity)
    db_config = {
        'type': 'sqlite',
        'database': 'data/olist.db'
    }
    
    # Initialize database connection
    db = DatabaseConnection(db_config)
    
    try:
        db.connect()
        logger.info("Database connection established")
        
        # Initialize data loader
        data_dir = Path("data")
        loader = DataLoader(db, str(data_dir))
        
        # Load all CSV files
        logger.info("\nStarting data loading process...")
        logger.info(f"Looking for CSV files in: {data_dir.absolute()}")
        
        results = loader.load_all_csv_files()
        
        # Verify data
        logger.info("\n" + "=" * 60)
        logger.info("Verifying loaded data...")
        logger.info("=" * 60)
        verification = loader.verify_data_loaded()
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Setup Summary")
        logger.info("=" * 60)
        total_rows = sum(verification.values())
        logger.info(f"Total rows loaded: {total_rows:,}")
        
        for table_name, row_count in verification.items():
            status = "[OK]" if row_count > 0 else "[FAIL]"
            logger.info(f"{status} {table_name}: {row_count:,} rows")
        
        if total_rows > 0:
            logger.info("\n[SUCCESS] Database setup completed successfully!")
            logger.info(f"Database location: {Path(db_config['database']).absolute()}")
        else:
            logger.warning("\n[WARNING] No data was loaded. Please check:")
            logger.warning("  1. CSV files are in the 'data/' directory")
            logger.warning("  2. CSV file names match expected names")
            logger.warning("  3. CSV files are not empty")
            
    except Exception as e:
        logger.error(f"Setup failed: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

