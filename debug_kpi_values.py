import sqlite3
import json
import numpy as np
from datetime import datetime

def debug_kpis():
    conn = sqlite3.connect('data/olist.db')
    
    # Load Config
    with open('config/kpi_config.json', 'r') as f:
        config = json.load(f)
        
    with open('debug_output_utf8.txt', 'w', encoding='utf-8') as outfile:
        outfile.write(f"Debug Run Time: {datetime.now()}\n")
        
        for kpi in config['kpis']:
            name = kpi['name']
            outfile.write(f"\n---------------------------------------------------\n")
            outfile.write(f"KPI: {name}\n")
            
            # 1. Get Current Value
            query = kpi['sql_query']
            try:
                cursor = conn.cursor()
                cursor.execute(query)
                res = cursor.fetchone()
                current_val = res[0] if res else None
                outfile.write(f"Current Value SQL: {query}\n")
                outfile.write(f"Current Value: {current_val}\n")
            except Exception as e:
                outfile.write(f"Error getting current value: {e}\n")
                continue

            # 2. Get Historical Values
            comparison = kpi.get('comparison_period', 'previous_week')
            outfile.write(f"Comparison Period: {comparison}\n")
            
            if name == 'daily_revenue':
                hist_query = """
                    SELECT DATE(o.order_purchase_timestamp) as date, SUM(op.payment_value)
                    FROM olist_order_payments_dataset op 
                    JOIN olist_orders_dataset o ON op.order_id = o.order_id 
                    WHERE o.order_status != 'canceled'
                    AND DATE(o.order_purchase_timestamp) >= DATE('now', '-14 days')
                    GROUP BY date
                    ORDER BY date DESC
                """
                cursor.execute(hist_query)
                rows = cursor.fetchall()
                outfile.write("History (Last 14 Days):\n")
                for r in rows:
                    outfile.write(f"  {r[0]}: {r[1]}\n")
                    
            elif name == 'daily_order_volume':
                hist_query = """
                    SELECT DATE(o.order_purchase_timestamp) as date, COUNT(DISTINCT o.order_id)
                    FROM olist_orders_dataset o
                    WHERE o.order_status != 'canceled'
                    AND DATE(o.order_purchase_timestamp) >= DATE('now', '-14 days')
                    GROUP BY date
                    ORDER BY date DESC
                """
                cursor.execute(hist_query)
                rows = cursor.fetchall()
                outfile.write("History (Last 14 Days):\n")
                for r in rows:
                    outfile.write(f"  {r[0]}: {r[1]}\n")

    conn.close()

if __name__ == "__main__":
    debug_kpis()
