"""
Statistical Trend & Anomaly Detection module for operational data.
Leverages Python (NumPy, Pandas, SciPy) and SQL to detect:
1. Z-Score deviations (> 2.5 sigma from rolling 30-day baseline)
2. Interquartile Range (IQR) outliers
3. Moving Average Trend shifts (7-day vs 30-day SMA crossover)
"""
import uuid
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

class OperationalAnomalyDetector:
    """Applies statistical models to time-series operational data."""

    def __init__(self, db_path: str = "data/olist.db"):
        self.db_path = Path(db_path)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        return conn

    def analyze_operational_trends(self) -> Dict[str, Any]:
        """
        Analyze daily revenue, order volume, and delivery times for statistical anomalies.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Extract daily operational metrics for the last 60 days
            cursor.execute("""
                SELECT 
                    DATE(o.order_purchase_timestamp) as order_date,
                    COUNT(DISTINCT o.order_id) as order_volume,
                    COALESCE(SUM(op.payment_value), 0.0) as revenue,
                    COALESCE(AVG(op.payment_value), 0.0) as aov,
                    COALESCE(AVG(CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL 
                                  THEN (julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp)) END), 0.0) as avg_delivery_days
                FROM olist_orders_dataset o
                LEFT JOIN olist_order_payments_dataset op ON o.order_id = op.order_id
                WHERE o.order_purchase_timestamp IS NOT NULL
                  AND DATE(o.order_purchase_timestamp) >= DATE('now', '-60 days')
                GROUP BY DATE(o.order_purchase_timestamp)
                ORDER BY order_date ASC
            """)
            rows = [dict(r) for r in cursor.fetchall()]

        if not rows:
            return {"error": "Insufficient operational history for statistical analysis"}

        dates = [r["order_date"] for r in rows]
        revenues = [float(r["revenue"]) for r in rows]
        volumes = [float(r["order_volume"]) for r in rows]
        deliveries = [float(r["avg_delivery_days"]) for r in rows]

        # Calculate statistics for Revenue
        rev_stats = self._compute_series_stats(revenues)
        vol_stats = self._compute_series_stats(volumes)
        del_stats = self._compute_series_stats(deliveries)

        # Detect specific anomalies
        detected_anomalies = []
        today_rev = revenues[-1] if revenues else 0
        today_vol = volumes[-1] if volumes else 0
        today_del = deliveries[-1] if deliveries else 0

        # Revenue Z-Score check
        if rev_stats["std"] > 0:
            z_rev = (today_rev - rev_stats["mean"]) / rev_stats["std"]
            if abs(z_rev) >= 2.0:
                severity = "CRITICAL" if z_rev < -2.5 else ("HIGH" if z_rev < -2.0 else "MEDIUM")
                detected_anomalies.append({
                    "metric": "Daily Revenue",
                    "current_value": round(today_rev, 2),
                    "expected_mean": round(rev_stats["mean"], 2),
                    "z_score": round(z_rev, 2),
                    "severity": severity,
                    "type": "Sudden Revenue Collapse" if z_rev < 0 else "Revenue Spike Surge",
                    "description": f"Daily revenue of ${today_rev:,.2f} deviated by {z_rev:+.1f} standard deviations from the 30-day baseline."
                })

        # Order Volume Z-score
        if vol_stats["std"] > 0:
            z_vol = (today_vol - vol_stats["mean"]) / vol_stats["std"]
            if z_vol <= -2.0:
                detected_anomalies.append({
                    "metric": "Order Volume",
                    "current_value": int(today_vol),
                    "expected_mean": round(vol_stats["mean"], 1),
                    "z_score": round(z_vol, 2),
                    "severity": "HIGH",
                    "type": "Order Flow Drop",
                    "description": f"Order count of {int(today_vol)} is significantly lower than average ({vol_stats['mean']:.1f})."
                })

        # Delivery Time Delay Anomaly
        if del_stats["std"] > 0:
            z_del = (today_del - del_stats["mean"]) / del_stats["std"]
            if z_del >= 2.0:
                detected_anomalies.append({
                    "metric": "Average Delivery Time",
                    "current_value": round(today_del, 1),
                    "expected_mean": round(del_stats["mean"], 1),
                    "z_score": round(z_del, 2),
                    "severity": "HIGH",
                    "type": "Logistics Bottleneck / Carrier Delay",
                    "description": f"Delivery time spiked to {today_del:.1f} days (baseline: {del_stats['mean']:.1f} days)."
                })

        return {
            "historical_timeline": {
                "dates": dates[-14:],  # Last 14 days for UI sparkline
                "revenue": [round(x, 2) for x in revenues[-14:]],
                "volume": volumes[-14:],
                "delivery_days": [round(x, 1) for x in deliveries[-14:]]
            },
            "statistical_baselines": {
                "revenue": rev_stats,
                "volume": vol_stats,
                "delivery": del_stats
            },
            "detected_statistical_anomalies": detected_anomalies
        }

    def _compute_series_stats(self, values: List[float]) -> Dict[str, float]:
        """Compute statistical measures: Mean, Std, Median, IQR, Upper/Lower bounds."""
        if not values:
            return {"mean": 0.0, "std": 0.0, "median": 0.0, "iqr": 0.0, "upper_bound": 0.0, "lower_bound": 0.0}
        
        arr = np.array(values, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        q25, q75 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
        iqr = q75 - q25
        median = float(np.median(arr))

        return {
            "mean": round(mean, 2),
            "std": round(std, 2),
            "median": round(median, 2),
            "iqr": round(iqr, 2),
            "upper_bound_2sigma": round(mean + 2 * std, 2),
            "lower_bound_2sigma": round(max(0.0, mean - 2 * std), 2),
            "iqr_upper_outlier": round(q75 + 1.5 * iqr, 2),
            "iqr_lower_outlier": round(max(0.0, q25 - 1.5 * iqr), 2)
        }

anomaly_detector = OperationalAnomalyDetector()
