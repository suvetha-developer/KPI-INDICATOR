import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def check_recent_data():
    conn = sqlite3.connect('data/olist.db')
    cursor = conn.cursor()
    
    print(f"Current System Time: {datetime.now()}")
    
    # Check last 7 days of data
    query = """
        SELECT DATE(order_purchase_timestamp) as date, COUNT(*), SUM(payment_value)
        FROM olist_orders_dataset o
        LEFT JOIN olist_order_payments_dataset op ON o.order_id = op.order_id
        WHERE DATE(order_purchase_timestamp) >= DATE('now', '-7 days')
        GROUP BY date
        ORDER BY date DESC
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    print("\nRecent Data Distribution:")
    print("Date | Order Count | Total Revenue")
    print("-" * 40)
    for row in results:
        print(f"{row[0]} | {row[1]} | {row[2]}")
        
    conn.close()

if __name__ == "__main__":
    check_recent_data()
