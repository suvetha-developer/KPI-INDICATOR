import sqlite3
import pandas as pd

def check_dates():
    conn = sqlite3.connect('data/olist.db')
    query = "SELECT MIN(order_purchase_timestamp), MAX(order_purchase_timestamp) FROM olist_orders_dataset"
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    print(f"Min Date: {result[0]}")
    print(f"Max Date: {result[1]}")
    conn.close()

if __name__ == "__main__":
    check_dates()
