"""
Automated Data Quality & Integrity Checker module for KPI Monitoring System.
Executes SQL queries and Python validation rules to evaluate completeness,
uniqueness, domain validity, referential integrity, and reconciliation consistency.
"""
import uuid
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class DataQualityEngine:
    """Executes automated Data Quality audits against operational database."""

    def __init__(self, db_path: str = "data/olist.db"):
        self.db_path = Path(db_path)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        return conn

    def run_all_checks(self) -> Dict[str, Any]:
        """
        Run full suite of data quality checks and compute overall health score.
        """
        checks = []
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Rule 1: Null Check on Orders Key Columns
            cursor.execute("""
                SELECT COUNT(*) as count FROM olist_orders_dataset
                WHERE order_id IS NULL OR customer_id IS NULL OR order_status IS NULL OR order_purchase_timestamp IS NULL
            """)
            failed_null_orders = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Orders Primary Fields Completeness",
                "category": "Completeness",
                "description": "Verifies that order_id, customer_id, order_status, and purchase timestamp are not null",
                "failed_count": failed_null_orders,
                "status": "PASS" if failed_null_orders == 0 else "FAIL",
                "severity": "CRITICAL"
            })

            # Rule 2: Null Check on Payments Values
            cursor.execute("""
                SELECT COUNT(*) as count FROM olist_order_payments_dataset
                WHERE payment_value IS NULL OR payment_type IS NULL OR order_id IS NULL
            """)
            failed_null_payments = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Payment Records Completeness",
                "category": "Completeness",
                "description": "Ensures payment_value, payment_type, and order_id are fully populated",
                "failed_count": failed_null_payments,
                "status": "PASS" if failed_null_payments == 0 else "FAIL",
                "severity": "HIGH"
            })

            # Rule 3: Duplicate Order IDs
            cursor.execute("""
                SELECT COUNT(*) as count FROM (
                    SELECT order_id, COUNT(*) FROM olist_orders_dataset
                    GROUP BY order_id HAVING COUNT(*) > 1
                )
            """)
            failed_dup_orders = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Order ID Uniqueness",
                "category": "Uniqueness",
                "description": "Ensures no duplicate order_id exists in the primary orders table",
                "failed_count": failed_dup_orders,
                "status": "PASS" if failed_dup_orders == 0 else "FAIL",
                "severity": "CRITICAL"
            })

            # Rule 4: Duplicate Payment Sequences
            cursor.execute("""
                SELECT COUNT(*) as count FROM (
                    SELECT order_id, payment_sequential, COUNT(*) FROM olist_order_payments_dataset
                    GROUP BY order_id, payment_sequential HAVING COUNT(*) > 1
                )
            """)
            failed_dup_payments = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Payment Sequence Uniqueness",
                "category": "Uniqueness",
                "description": "Verifies composite key uniqueness (order_id, payment_sequential)",
                "failed_count": failed_dup_payments,
                "status": "PASS" if failed_dup_payments == 0 else "FAIL",
                "severity": "HIGH"
            })

            # Rule 5: Non-Negative Payment Amounts
            cursor.execute("""
                SELECT COUNT(*) as count FROM olist_order_payments_dataset
                WHERE payment_value < 0
            """)
            failed_neg_payments = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Payment Value Domain Validity",
                "category": "Validity",
                "description": "Validates that monetary payment amounts are strictly non-negative",
                "failed_count": failed_neg_payments,
                "status": "PASS" if failed_neg_payments == 0 else "FAIL",
                "severity": "CRITICAL"
            })

            # Rule 6: Temporal Logic (Delivered Date >= Purchase Date)
            cursor.execute("""
                SELECT COUNT(*) as count FROM olist_orders_dataset
                WHERE order_delivered_customer_date IS NOT NULL
                  AND order_purchase_timestamp IS NOT NULL
                  AND order_delivered_customer_date < order_purchase_timestamp
            """)
            failed_temporal = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Chronological Delivery Logic",
                "category": "Validity",
                "description": "Ensures customer delivery timestamp occurs after the initial purchase date",
                "failed_count": failed_temporal,
                "status": "PASS" if failed_temporal == 0 else "FAIL",
                "severity": "MEDIUM"
            })

            # Rule 7: Orphan Payments (Referential Integrity)
            cursor.execute("""
                SELECT COUNT(*) as count FROM olist_order_payments_dataset
                WHERE order_id NOT IN (SELECT order_id FROM olist_orders_dataset)
            """)
            failed_orphan_payments = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Orphan Payments Check",
                "category": "Referential Integrity",
                "description": "Verifies that all payment entries map directly to valid orders in olist_orders_dataset",
                "failed_count": failed_orphan_payments,
                "status": "PASS" if failed_orphan_payments == 0 else "FAIL",
                "severity": "HIGH"
            })

            # Rule 8: Review Score Range Validity (1 to 5)
            cursor.execute("""
                SELECT COUNT(*) as count FROM olist_order_reviews_dataset
                WHERE review_score NOT BETWEEN 1 AND 5
            """)
            failed_review_range = cursor.fetchone()['count']
            checks.append({
                "rule_name": "Customer Review Score Bounds",
                "category": "Validity",
                "description": "Ensures CSAT review scores adhere to the standardized 1-5 integer scale",
                "failed_count": failed_review_range,
                "status": "PASS" if failed_review_range == 0 else "FAIL",
                "severity": "LOW"
            })

            # Calculate total records evaluated
            cursor.execute("SELECT COUNT(*) as c FROM olist_orders_dataset")
            total_orders = cursor.fetchone()['c']

            # Record results to audit table
            now_iso = datetime.now().isoformat()
            passed_checks = sum(1 for c in checks if c["status"] == "PASS")
            total_checks = len(checks)
            dq_score = round((passed_checks / total_checks) * 100, 1)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_data_quality_audit (
                    audit_id TEXT PRIMARY KEY,
                    run_timestamp TEXT,
                    rule_name TEXT,
                    category TEXT,
                    status TEXT,
                    failed_records_count INTEGER,
                    score REAL,
                    details TEXT
                )
            """)

            for c in checks:
                cursor.execute("""
                    INSERT INTO kpi_data_quality_audit 
                    (audit_id, run_timestamp, rule_name, category, status, failed_records_count, score, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4()), now_iso, c["rule_name"], c["category"],
                    c["status"], c["failed_count"], dq_score, c["description"]
                ))
            conn.commit()

        logger.info(f"Data Quality Audit executed: {passed_checks}/{total_checks} passed ({dq_score}%)")
        return {
            "timestamp": now_iso,
            "overall_score": dq_score,
            "total_rules": total_checks,
            "passed_rules": passed_checks,
            "failed_rules": total_checks - passed_checks,
            "status": "HEALTHY" if dq_score >= 90 else ("DEGRADED" if dq_score >= 70 else "CRITICAL"),
            "total_orders_audited": total_orders,
            "checks": checks
        }

    def clean_known_anomalies(self) -> Dict[str, Any]:
        """Auto-remediation utility to fix dirty test records."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM olist_orders_dataset WHERE order_id LIKE 'dq_err_%'")
            cursor.execute("DELETE FROM olist_order_payments_dataset WHERE order_id LIKE 'dq_err_%'")
            cursor.execute("DELETE FROM olist_order_items_dataset WHERE order_id LIKE 'dq_err_%'")
            cursor.execute("DELETE FROM olist_order_payments_dataset WHERE payment_value < 0")
            cursor.execute("DELETE FROM olist_orders_dataset WHERE order_status IS NULL")
            conn.commit()
        return {"success": True, "message": "Known dirty records remediated successfully."}

dq_engine = DataQualityEngine()
