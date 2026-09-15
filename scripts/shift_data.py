import sqlite3
from datetime import datetime
import pandas as pd

def shift_dates():
    db_path = 'data/olist.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Connecting to database...")
    
    # 1. Get the latest date in the current dataset
    cursor.execute("SELECT MAX(order_purchase_timestamp) FROM olist_orders_dataset")
    max_date_str = cursor.fetchone()[0]
    max_date = datetime.strptime(max_date_str, '%Y-%m-%d %H:%M:%S')
    
    # 2. Calculate the shift needed to bring data to today
    now = datetime.now()
    # Shift so the last order happened "yesterday" (to ensure we see completed data)
    # or just shift to "now". Let's shift so the max date aligns with NOW.
    time_delta = now - max_date
    days_shift = time_delta.days
    
    print(f"Current Max Date: {max_date}")
    print(f"Target Date: {now}")
    print(f"Shifting data forward by approximately {days_shift} days...")
    
    # 3. Define tables and columns to update
    tables_columns = {
        'olist_orders_dataset': [
            'order_purchase_timestamp',
            'order_approved_at',
            'order_delivered_carrier_date',
            'order_delivered_customer_date',
            'order_estimated_delivery_date'
        ],
        'olist_order_reviews_dataset': [
            'review_creation_date',
            'review_answer_timestamp'
        ],
        'olist_order_items_dataset': [
            'shipping_limit_date'
        ]
    }
    
    try:
        # SQLite doesn't have a simple INTERVAL syntax for updates that works consistently across versions
        # safely like postgres, but we can use the 'datetime' modifier string.
        # We'll construct the modifier string: '+X days'
        
        modifier = f"+{days_shift} days"
        
        # We also need to account for seconds/minutes if we want precision, 
        # but days is usually enough for KPI dashboard demo.
        # Let's use the exact seconds shift if we can, but simpler is safer for sqlite string manipulation.
        # Let's stick to days for simplicity and robustness.
        
        cursor.execute("BEGIN TRANSACTION")
        
        for table, columns in tables_columns.items():
            for col in columns:
                print(f"Updating {table}.{col}...")
                # SQLite datetime function: datetime(col, '+N days')
                query = f"""
                    UPDATE {table} 
                    SET {col} = datetime({col}, '{modifier}')
                    WHERE {col} IS NOT NULL
                """
                cursor.execute(query)
                
        conn.commit()
        print("Successfully shifted all dates!")
        
        # Verify new max date
        cursor.execute("SELECT MAX(order_purchase_timestamp) FROM olist_orders_dataset")
        new_max_date = cursor.fetchone()[0]
        print(f"New Max Date: {new_max_date}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error shifting data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    shift_dates()
