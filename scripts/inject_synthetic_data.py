import sqlite3
import random
import uuid
from datetime import datetime, timedelta

def inject_churn_data():
    db_path = 'data/olist.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Injecting High Churn & Anomaly Data...")
    
    # 1. SETUP DATES
    today = datetime.now()
    # Windows for Churn Calculation:
    # Reference Window: [Today-60, Today-30)
    # Current Window:   [Today-30, Today)
    
    window_ref_start = today - timedelta(days=60)
    window_ref_end   = today - timedelta(days=30)
    window_curr_start = window_ref_end
    window_curr_end   = today
    
    # 2. CLEAR RECENT DATA (Clear last 70 days to be safe)
    clean_from = (today - timedelta(days=70)).strftime('%Y-%m-%d')
    print(f"Clearing order data from {clean_from}...")
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.execute("DELETE FROM olist_orders_dataset WHERE DATE(order_purchase_timestamp) >= ?", (clean_from,))
    cursor.execute("DELETE FROM olist_order_payments_dataset WHERE order_id NOT IN (SELECT order_id FROM olist_orders_dataset)")
    cursor.execute("DELETE FROM olist_order_items_dataset WHERE order_id NOT IN (SELECT order_id FROM olist_orders_dataset)")
    
    # 3. CREATE CUSTOMER POOLS
    # We need to insert them into DB first to be valid FKs (though we disabled FKs, good practice)
    def create_customers(count, prefix):
        ids = []
        for i in range(count):
            cid = f"{prefix}_{uuid.uuid4().hex[:8]}"
            ids.append(cid)
            cursor.execute("INSERT OR IGNORE INTO olist_customers_dataset (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state) VALUES (?, ?, '00000', 'Test City', 'XX')", (cid, cid))
        return ids

    print("Creating customer segments...")
    # Group A: CHURNED (Bought in Ref Window, NOT in Curr Window) -> HIGH Churn
    # Let's say 800 customers churned.
    churn_customers = create_customers(800, "churn")
    
    # Group B: RETAINED (Bought in Ref Window AND in Curr Window)
    # Let's say 200 customers retained.
    # Total Base = 1000. Churn = 800. Rate = 80%.
    retained_customers = create_customers(200, "retained")
    
    # Group C: NEW (Bought ONLY in Curr Window)
    # Keeps volume up so revenue looks okay-ish, or low if we want revenue alert too.
    # User wanted "Warning Message" -> Churn Warning + Revenue Warning?
    # Let's make Revenue somewhat low today as well to keep that previous alert.
    new_customers = create_customers(500, "new")
    
    # 4. GENERATE ORDERS
    
    def generate_orders_for_users(users, start_date, end_date, avg_orders_per_user=1):
        total_days = (end_date - start_date).days
        count = 0
        for uid in users:
            # Random # of orders
            n = max(1, int(random.gauss(avg_orders_per_user, 0.5)))
            for _ in range(n):
                # Random time in window
                day_offset = random.randint(0, total_days)
                order_time = start_date + timedelta(days=day_offset, hours=random.randint(9, 20))
                order_time_str = order_time.strftime('%Y-%m-%d %H:%M:%S')
                
                oid = str(uuid.uuid4())
                
                # Insert Order
                cursor.execute("""
                    INSERT INTO olist_orders_dataset (
                        order_id, customer_id, order_status, order_purchase_timestamp,
                        order_approved_at, order_delivered_carrier_date, order_delivered_customer_date,
                        order_estimated_delivery_date
                    ) VALUES (?, ?, 'delivered', ?, ?, ?, ?, ?)
                """, (oid, uid, order_time_str, order_time_str, order_time_str, order_time_str, order_time_str))
                
                # Payment
                val = random.uniform(50, 150)
                cursor.execute("INSERT INTO olist_order_payments_dataset (order_id, payment_sequential, payment_type, payment_installments, payment_value) VALUES (?, 1, 'credit_card', 1, ?)", (oid, val))
                
                # Item
                cursor.execute("INSERT INTO olist_order_items_dataset (order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value) VALUES (?, 1, 'prod_test', 'seller_test', ?, ?, 10)", (oid, order_time_str, val))
                count += 1
        return count

    print("Generating Historical Reference Orders (60-30 days ago)...")
    # Both Churn and Retained groups active here
    c1 = generate_orders_for_users(churn_customers, window_ref_start, window_ref_end, avg_orders_per_user=2)
    c2 = generate_orders_for_users(retained_customers, window_ref_start, window_ref_end, avg_orders_per_user=2)
    print(f"  -> {c1 + c2} orders in reference window.")

    print("Generating Recent Orders (30-0 days ago)...")
    # Only Retained and New groups active here (Churn group is silent = CHURN!)
    # To keep "Revenue Anomaly" for TODAY (user asked for warning), keep volume low specifically for LAST 2 DAYS.
    
    window_curr_active_end = today - timedelta(days=2) # Up to 2 days ago normally
    
    c3 = generate_orders_for_users(retained_customers, window_curr_start, window_curr_active_end, avg_orders_per_user=2)
    c4 = generate_orders_for_users(new_customers, window_curr_start, window_curr_active_end, avg_orders_per_user=2)
    print(f"  -> {c3 + c4} orders in recent window (excluding today).")
    
    # 5. GENERATE TODAY'S ANOMALY (Low Revenue)
    # Add just a few orders for today/yesterday to show 'activity' but trigger Low Revenue Alert
    print("Generating Today's Low Activity (Revenue Anomaly)...")
    recent_active_users = retained_customers[:10] + new_customers[:10]
    c5 = generate_orders_for_users(recent_active_users, today - timedelta(days=1), today, avg_orders_per_user=1)
    print(f"  -> {c5} orders for today/yesterday (LOW).")
    
    conn.commit()
    conn.close()
    
    print("\nSUMMARY:")
    print(f"  Reference Base Customers (60-30d ago): {len(churn_customers) + len(retained_customers)}")
    print(f"  Lost Customers (30-0d ago): {len(churn_customers)}")
    print(f"  Expected Churn Rate: {len(churn_customers) / (len(churn_customers) + len(retained_customers)) * 100:.1f}%")
    print("  Revenue Alert: Active (Today's volume low).")
    print("Done.")

if __name__ == "__main__":
    inject_churn_data()
