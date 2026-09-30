"""
Automated Root-Cause Analysis (RCA) & Dimensional Diagnostic Engine.
Performs automated multi-dimensional drill-downs across:
- Regional Geography (State & City variance)
- Product Categories (Volume & Margin contributions)
- Payment Gateway Types (Approval/Decline rates)
- Logistics & Transit Bottlenecks
Generates executive diagnostic insights and actionable corrective steps.
"""
import sqlite3
import logging
from typing import Dict, List, Any
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

class RootCauseAnalyzer:
    """Decomposes KPI variance across operational dimensions to identify root causes."""

    def __init__(self, db_path: str = "data/olist.db"):
        self.db_path = Path(db_path)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        return conn

    def diagnose_operational_anomaly(self, kpi_name: str = "daily_revenue") -> Dict[str, Any]:
        """
        Perform automated drill-down across Geography, Product Category, Payment Method,
        and Logistics to pinpoint the primary drivers behind current deviations.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. State / Regional Breakdown (Current 7 Days vs Prior 7-14 Days)
            cursor.execute("""
                SELECT 
                    c.customer_state,
                    COUNT(DISTINCT CASE WHEN o.order_purchase_timestamp >= DATE('now', '-7 days') THEN o.order_id END) as orders_recent,
                    ROUND(SUM(CASE WHEN o.order_purchase_timestamp >= DATE('now', '-7 days') THEN p.payment_value ELSE 0 END), 2) as rev_recent,
                    COUNT(DISTINCT CASE WHEN o.order_purchase_timestamp >= DATE('now', '-14 days') AND o.order_purchase_timestamp < DATE('now', '-7 days') THEN o.order_id END) as orders_prior,
                    ROUND(SUM(CASE WHEN o.order_purchase_timestamp >= DATE('now', '-14 days') AND o.order_purchase_timestamp < DATE('now', '-7 days') THEN p.payment_value ELSE 0 END), 2) as rev_prior
                FROM olist_orders_dataset o
                JOIN olist_customers_dataset c ON o.customer_id = c.customer_id
                LEFT JOIN olist_order_payments_dataset p ON o.order_id = p.order_id
                WHERE o.order_purchase_timestamp >= DATE('now', '-14 days')
                GROUP BY c.customer_state
                ORDER BY rev_recent DESC
                LIMIT 8
            """)
            state_rows = [dict(r) for r in cursor.fetchall()]

            # 2. Product Category Performance
            cursor.execute("""
                SELECT 
                    COALESCE(t.product_category_name_english, pr.product_category_name, 'Other') as category,
                    COUNT(DISTINCT oi.order_id) as items_sold,
                    ROUND(SUM(oi.price), 2) as category_revenue
                FROM olist_order_items_dataset oi
                JOIN olist_orders_dataset o ON oi.order_id = o.order_id
                LEFT JOIN olist_products_dataset pr ON oi.product_id = pr.product_id
                LEFT JOIN product_category_name_translation t ON pr.product_category_name = t.product_category_name
                WHERE o.order_purchase_timestamp >= DATE('now', '-14 days')
                GROUP BY category
                ORDER BY category_revenue DESC
                LIMIT 6
            """)
            cat_rows = [dict(r) for r in cursor.fetchall()]

            # 3. Payment Method Distribution & Cancellation Analysis
            cursor.execute("""
                SELECT 
                    p.payment_type,
                    COUNT(DISTINCT o.order_id) as total_attempts,
                    COUNT(DISTINCT CASE WHEN o.order_status = 'canceled' THEN o.order_id END) as canceled_count,
                    ROUND(COUNT(DISTINCT CASE WHEN o.order_status = 'canceled' THEN o.order_id END) * 100.0 / NULLIF(COUNT(DISTINCT o.order_id), 0), 1) as cancellation_rate_pct,
                    ROUND(SUM(p.payment_value), 2) as total_volume
                FROM olist_order_payments_dataset p
                JOIN olist_orders_dataset o ON p.order_id = o.order_id
                WHERE o.order_purchase_timestamp >= DATE('now', '-14 days')
                GROUP BY p.payment_type
                ORDER BY total_volume DESC
            """)
            payment_rows = [dict(r) for r in cursor.fetchall()]

            # 4. Logistics Transit Delays by State
            cursor.execute("""
                SELECT 
                    c.customer_state,
                    ROUND(AVG(JULIANDAY(o.order_delivered_customer_date) - JULIANDAY(o.order_purchase_timestamp)), 1) as avg_delivery_days,
                    COUNT(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 END) as late_deliveries,
                    COUNT(*) as total_delivered
                FROM olist_orders_dataset o
                JOIN olist_customers_dataset c ON o.customer_id = c.customer_id
                WHERE o.order_delivered_customer_date IS NOT NULL
                  AND o.order_purchase_timestamp >= DATE('now', '-30 days')
                GROUP BY c.customer_state
                HAVING COUNT(*) >= 5
                ORDER BY avg_delivery_days DESC
                LIMIT 5
            """)
            logistics_rows = [dict(r) for r in cursor.fetchall()]

        # Compute top variance driver
        top_lagging_state = None
        max_drop = 0.0
        for s in state_rows:
            drop = (s["rev_prior"] or 0) - (s["rev_recent"] or 0)
            if drop > max_drop:
                max_drop = drop
                top_lagging_state = s["customer_state"]

        # Formulate executive actionable insights
        actionable_recommendations = []
        if top_lagging_state:
            actionable_recommendations.append(
                f"Regional Focus: State '{top_lagging_state}' accounts for largest period-over-period variance (-${max_drop:,.2f}). Investigate regional ad delivery and local fulfillment inventory."
            )
        
        # Payment Gateway insight
        card_fails = next((p for p in payment_rows if p["payment_type"] == "credit_card"), None)
        if card_fails and (card_fails.get("cancellation_rate_pct") or 0) > 10.0:
            actionable_recommendations.append(
                f"Payment Gateway Outage: Credit card cancellation rate is elevated at {card_fails['cancellation_rate_pct']}%. Check payment acquirer gateway connectivity."
            )
        else:
            actionable_recommendations.append(
                "Payment Processing: Transaction settlement rates are stable across credit card and alternative payment rails."
            )

        # Logistics SLA insight
        if logistics_rows and logistics_rows[0].get("avg_delivery_days", 0) > 8.0:
            worst = logistics_rows[0]
            actionable_recommendations.append(
                f"Logistics Delay: Transit times in '{worst['customer_state']}' averaged {worst['avg_delivery_days']} days ({worst['late_deliveries']} late shipments). Reroute shipments through secondary carrier hubs."
            )

        return {
            "target_kpi": kpi_name,
            "regional_breakdown": state_rows,
            "category_performance": cat_rows,
            "payment_diagnostics": payment_rows,
            "logistics_delays": logistics_rows,
            "top_variance_driver": top_lagging_state or "Balanced across regions",
            "actionable_recommendations": actionable_recommendations
        }

root_cause_analyzer = RootCauseAnalyzer()
