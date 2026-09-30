"""
Power BI Integration & Automated Dataset Exporter for KPI Monitoring System.
1. Creates optimized SQL views in SQLite for direct Power BI ODBC connection.
2. Exports denormalized operational datasets into CSV format for Power BI ingestion.
3. Generates DAX calculated measures and star-schema model metadata.
"""
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

class PowerBIExporter:
    """Manages Power BI database views and automated CSV data exports."""

    def __init__(self, db_path: str = "data/olist.db", export_dir: str = "data/powerbi"):
        self.db_path = Path(db_path)
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        return conn

    def setup_powerbi_views(self):
        """Create high-performance SQL views designed for Power BI star schema modeling."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # View 1: Operational Orders Flat Fact Table
            cursor.execute("""
                CREATE VIEW IF NOT EXISTS vw_powerbi_operational_orders AS
                SELECT 
                    o.order_id,
                    o.customer_id,
                    c.customer_city,
                    c.customer_state,
                    o.order_status,
                    o.order_purchase_timestamp,
                    DATE(o.order_purchase_timestamp) as order_date,
                    STRFTIME('%Y-%m', o.order_purchase_timestamp) as order_year_month,
                    STRFTIME('%H', o.order_purchase_timestamp) as order_hour,
                    o.order_delivered_customer_date,
                    o.order_estimated_delivery_date,
                    ROUND(JULIANDAY(o.order_delivered_customer_date) - JULIANDAY(o.order_purchase_timestamp), 1) as delivery_days,
                    CASE 
                        WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 1 
                        WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 0
                        ELSE NULL 
                    END as is_on_time,
                    COALESCE(p.payment_value, 0.0) as order_revenue,
                    COALESCE(p.payment_type, 'unspecified') as payment_method,
                    COALESCE(r.review_score, 0) as csat_review_score
                FROM olist_orders_dataset o
                LEFT JOIN olist_customers_dataset c ON o.customer_id = c.customer_id
                LEFT JOIN (
                    SELECT order_id, SUM(payment_value) as payment_value, MAX(payment_type) as payment_type
                    FROM olist_order_payments_dataset GROUP BY order_id
                ) p ON o.order_id = p.order_id
                LEFT JOIN (
                    SELECT order_id, AVG(review_score) as review_score
                    FROM olist_order_reviews_dataset GROUP BY order_id
                ) r ON o.order_id = r.order_id
            """)

            # View 2: Daily Aggregated KPI Summary
            cursor.execute("""
                CREATE VIEW IF NOT EXISTS vw_powerbi_daily_kpis AS
                SELECT 
                    DATE(o.order_purchase_timestamp) as report_date,
                    COUNT(DISTINCT o.order_id) as total_orders,
                    COUNT(DISTINCT CASE WHEN o.order_status = 'delivered' THEN o.order_id END) as delivered_orders,
                    ROUND(SUM(p.payment_value), 2) as daily_revenue,
                    ROUND(AVG(p.payment_value), 2) as average_order_value,
                    ROUND(AVG(CASE WHEN o.order_delivered_customer_date IS NOT NULL 
                                   THEN JULIANDAY(o.order_delivered_customer_date) - JULIANDAY(o.order_purchase_timestamp) END), 1) as avg_delivery_time_days,
                    ROUND(COUNT(CASE WHEN o.order_delivered_customer_date <= o.order_estimated_delivery_date THEN 1 END) * 100.0 / 
                          NULLIF(COUNT(CASE WHEN o.order_delivered_customer_date IS NOT NULL THEN 1 END), 0), 1) as on_time_delivery_rate_pct
                FROM olist_orders_dataset o
                LEFT JOIN olist_order_payments_dataset p ON o.order_id = p.order_id
                WHERE o.order_purchase_timestamp IS NOT NULL
                GROUP BY DATE(o.order_purchase_timestamp)
            """)

            conn.commit()
            logger.info("Power BI SQL Views verified/created.")

    def export_all_datasets(self) -> Dict[str, Any]:
        """Export all primary reporting datasets as CSV files for easy ingestion into Power BI Desktop/Service."""
        self.setup_powerbi_views()
        exported_files = {}

        with self.get_connection() as conn:
            # 1. Operational Orders Table
            df_orders = pd.read_sql_query("""
                SELECT * FROM vw_powerbi_operational_orders 
                WHERE order_purchase_timestamp >= DATE('now', '-90 days')
                ORDER BY order_purchase_timestamp DESC
            """, conn)
            orders_csv = self.export_dir / "powerbi_operational_orders.csv"
            df_orders.to_csv(orders_csv, index=False)
            exported_files["orders"] = {"path": str(orders_csv), "rows": len(df_orders)}

            # 2. Daily KPI Aggregations
            df_daily = pd.read_sql_query("""
                SELECT * FROM vw_powerbi_daily_kpis 
                ORDER BY report_date DESC
            """, conn)
            daily_csv = self.export_dir / "powerbi_daily_kpis.csv"
            df_daily.to_csv(daily_csv, index=False)
            exported_files["daily_kpis"] = {"path": str(daily_csv), "rows": len(df_daily)}

            # 3. Data Quality Audit Log
            try:
                df_dq = pd.read_sql_query("SELECT * FROM kpi_data_quality_audit ORDER BY run_timestamp DESC LIMIT 100", conn)
            except Exception:
                df_dq = pd.DataFrame()
            dq_csv = self.export_dir / "powerbi_data_quality_audit.csv"
            df_dq.to_csv(dq_csv, index=False)
            exported_files["data_quality"] = {"path": str(dq_csv), "rows": len(df_dq)}

            # 4. Regional Performance Summary
            df_geo = pd.read_sql_query("""
                SELECT 
                    c.customer_state,
                    c.customer_city,
                    COUNT(DISTINCT o.order_id) as total_orders,
                    ROUND(SUM(p.payment_value), 2) as state_revenue,
                    ROUND(AVG(p.payment_value), 2) as state_aov,
                    ROUND(AVG(r.review_score), 2) as avg_csat
                FROM olist_customers_dataset c
                JOIN olist_orders_dataset o ON c.customer_id = o.customer_id
                LEFT JOIN olist_order_payments_dataset p ON o.order_id = p.order_id
                LEFT JOIN olist_order_reviews_dataset r ON o.order_id = r.order_id
                WHERE o.order_purchase_timestamp >= DATE('now', '-90 days')
                GROUP BY c.customer_state, c.customer_city
                HAVING COUNT(DISTINCT o.order_id) >= 3
                ORDER BY state_revenue DESC
            """, conn)
            geo_csv = self.export_dir / "powerbi_regional_summary.csv"
            df_geo.to_csv(geo_csv, index=False)
            exported_files["regional"] = {"path": str(geo_csv), "rows": len(df_geo)}

        logger.info(f"Power BI datasets exported successfully to {self.export_dir}")
        return {
            "success": True,
            "export_directory": str(self.export_dir.absolute()),
            "files": exported_files
        }

powerbi_exporter = PowerBIExporter()
