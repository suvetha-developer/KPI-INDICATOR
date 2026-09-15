import sys
import pandas as pd
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import DatabaseConnection
from src.data_loader import DataLoader

def load_data():
    csv_path = Path('data/realtime_ecommerce_2025.csv')
    if not csv_path.exists():
        print(f"Error: {csv_path} not found.")
        return

    print("Reading new dataset...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows.")

    db_config = {'type': 'sqlite', 'database': 'data/olist.db'}
    db = DatabaseConnection(db_config)
    db.connect()

    # Reuse DataLoader to create schema (empty tables)
    loader = DataLoader(db)
    loader.create_schema()
    
    print("Transforming and loading data...")
    conn = db.connection
    cursor = conn.cursor()

    # Mappings
    status_map = {
        'Delivered': 'delivered',
        'Shipped': 'shipped',
        'Processing': 'processing', 
        'Cancelled': 'canceled',
        'Pending': 'invoiced'
    }

    # Tracking sets to avoid duplicate inserts for dimension tables
    existing_customers = set()
    existing_products = set()
    existing_sellers = set() # We'll just create one default seller

    # Default Seller
    default_seller_id = "seller_default_2025"
    cursor.execute("INSERT OR IGNORE INTO olist_sellers_dataset (seller_id, seller_zip_code_prefix, seller_city, seller_state) VALUES (?, ?, ?, ?)",
                   (default_seller_id, "00000", "New York", "NY"))

    orders_count = 0
    
    # Base date for reconstruction (Today)
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    def fix_timestamp(ts_str):
        # Format in CSV seems to be HH:MM.S or similar.
        # Example: '13:41.9'. We interpret this as 13:41 (1:41 PM).
        try:
            parts = str(ts_str).split('.')
            main_time = parts[0] # 13:41
            return f"{today_str} {main_time}:00"
        except:
            return f"{today_str} 00:00:00"

    try:
        for index, row in df.iterrows():
            # 1. Customer
            customer_id = str(row['customer_id'])
            if customer_id not in existing_customers:
                city = row.get('city', 'Unknown')
                cursor.execute("""
                    INSERT OR IGNORE INTO olist_customers_dataset 
                    (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
                    VALUES (?, ?, ?, ?, ?)
                """, (customer_id, customer_id, "00000", city, "XX"))
                existing_customers.add(customer_id)

            # 2. Product
            product_id = str(row['product_id'])
            if product_id not in existing_products:
                category = row.get('category', 'others')
                cursor.execute("""
                    INSERT OR IGNORE INTO olist_products_dataset
                    (product_id, product_category_name, product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (product_id, category, 0, 0, 0, 100, 10, 10, 10))
                existing_products.add(product_id)

            # 3. Order
            order_id = str(row['order_id'])
            raw_status = row.get('delivery_status', 'Pending')
            status = status_map.get(raw_status, 'processing')
            
            # Handle is_returned
            if str(row.get('is_returned')).lower() in ['yes', 'true', '1']:
                status = 'canceled'

            purchase_ts = fix_timestamp(row['order_timestamp'])
            
            # Estimate timestamps based on status for consistency
            approved_at = purchase_ts if status != 'canceled' else None
            delivered_carrier = purchase_ts if status in ['shipped', 'delivered'] else None
            delivered_customer = purchase_ts if status == 'delivered' else None
            estimated_delivery = purchase_ts # Placeholder

            cursor.execute("""
                INSERT OR REPLACE INTO olist_orders_dataset
                (order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_id, customer_id, status, purchase_ts, approved_at, delivered_carrier, delivered_customer, estimated_delivery))

            # 4. Payment
            order_value = float(row.get('order_value', 0))
            payment_method = row.get('payment_method', 'credit_card').lower().replace(' ', '_')
            
            cursor.execute("""
                INSERT OR REPLACE INTO olist_order_payments_dataset
                (order_id, payment_sequential, payment_type, payment_installments, payment_value)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, 1, payment_method, 1, order_value))

            # 5. Order Items
            # If quantity > 1, strictly we should show multiple items.
            # But the dataset flat row implies one product. 
            # If quantity > 1, we Loop.
            quantity = int(row.get('quantity', 1))
            price = float(row.get('price', 0))
            
            for i in range(1, quantity + 1):
                cursor.execute("""
                    INSERT OR REPLACE INTO olist_order_items_dataset
                    (order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (order_id, i, product_id, default_seller_id, purchase_ts, price, 0))

            orders_count += 1
            if orders_count % 1000 == 0:
                print(f"Processed {orders_count} orders...")

        conn.commit()
        print(f"Successfully loaded {orders_count} orders from 2025 dataset.")

    except Exception as e:
        conn.rollback()
        print(f"Error loading data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    load_data()
