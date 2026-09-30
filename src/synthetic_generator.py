"""
Real-Time Synthetic Dataset Generator for Automated KPI Monitoring & Alert System.
Simulates live operational e-commerce data streams (orders, payments, items, reviews, logistics)
and supports targeted statistical anomaly injection (revenue drops, churn spikes, delivery delays).
"""
import uuid
import random
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class RealtimeSyntheticGenerator:
    """Simulates real-time e-commerce operational data streams and statistical anomalies."""
    
    CITIES = [
        ("sao paulo", "SP"), ("rio de janeiro", "RJ"), ("belo horizonte", "MG"),
        ("brasilia", "DF"), ("curitiba", "PR"), ("porto alegre", "RS"),
        ("salvador", "BA"), ("campinas", "SP"), ("recife", "PE"), ("fortaleza", "CE")
    ]
    
    CATEGORIES = [
        "beleza_saude", "informatica_acessorios", "cama_mesa_banho",
        "esporte_lazer", "moveis_decoracao", "utilidades_domesticas",
        "telefonia", "automotivo", "brinquedos", "eletronicos"
    ]
    
    PAYMENT_TYPES = ["credit_card", "boleto", "voucher", "debit_card"]

    def __init__(self, db_path: str = "data/olist.db"):
        self.db_path = Path(db_path)
        self.is_streaming = False
        self.stream_thread: Optional[threading.Thread] = None
        self.stream_interval = 5.0  # seconds between simulated events
        self.stream_mode = "NORMAL" # NORMAL, REVENUE_DROP, CHURN_SPIKE, DELIVERY_DELAY, PAYMENT_FAIL
        self.stats = {
            "total_orders_injected": 0,
            "total_revenue_injected": 0.0,
            "last_injected_at": None,
            "stream_started_at": None,
            "active_mode": "NORMAL"
        }
        self._lock = threading.Lock()

    def get_connection(self) -> sqlite3.Connection:
        """Create a thread-safe connection with PRAGMA settings."""
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_auxiliary_tables(self):
        """Create audit & tracking tables if they don't already exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_synthetic_event_log (
                    event_id TEXT PRIMARY KEY,
                    event_timestamp TEXT,
                    scenario TEXT,
                    orders_count INTEGER,
                    total_value REAL,
                    notes TEXT
                )
            """)
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_anomaly_events (
                    anomaly_id TEXT PRIMARY KEY,
                    detected_at TEXT,
                    kpi_name TEXT,
                    current_value REAL,
                    baseline_mean REAL,
                    z_score REAL,
                    severity TEXT,
                    description TEXT
                )
            """)
            conn.commit()

    def generate_single_order(self, mode: str = "NORMAL", order_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Generate a single operational order record with related customer, payment, item, and review.
        """
        if order_time is None:
            order_time = datetime.now()
            
        order_time_str = order_time.strftime('%Y-%m-%d %H:%M:%S')
        order_id = f"syn_ord_{uuid.uuid4().hex[:12]}"
        cust_id = f"syn_cst_{uuid.uuid4().hex[:10]}"
        unique_id = f"syn_u_{uuid.uuid4().hex[:8]}"
        
        city, state = random.choice(self.CITIES)
        zip_prefix = f"{random.randint(10000, 99999)}"
        
        # Scenario adjustments
        if mode == "REVENUE_DROP":
            # Very small order value or canceled order
            payment_val = round(random.uniform(5.0, 18.0), 2)
            order_status = random.choices(["canceled", "unavailable", "delivered"], weights=[0.4, 0.3, 0.3])[0]
        elif mode == "PAYMENT_FAIL":
            payment_val = round(random.uniform(50.0, 250.0), 2)
            order_status = "canceled" # payment rejected
        else:
            payment_val = round(random.uniform(45.0, 320.0), 2)
            order_status = random.choices(["delivered", "shipped", "approved", "processing"], weights=[0.80, 0.12, 0.05, 0.03])[0]

        # Delivery logistics calculation
        if mode == "DELIVERY_DELAY":
            # Significant bottleneck: 12-25 days delivery time, breaching estimated date
            carrier_delay = random.randint(3, 7)
            transit_days = random.randint(10, 18)
            est_days = 8
        else:
            carrier_delay = random.randint(1, 2)
            transit_days = random.randint(2, 6)
            est_days = 12

        carrier_date = order_time + timedelta(days=carrier_delay)
        cust_delivered = order_time + timedelta(days=transit_days)
        estimated_date = order_time + timedelta(days=est_days)

        carrier_str = carrier_date.strftime('%Y-%m-%d %H:%M:%S') if order_status in ["shipped", "delivered"] else None
        cust_delivered_str = cust_delivered.strftime('%Y-%m-%d %H:%M:%S') if order_status == "delivered" else None
        est_str = estimated_date.strftime('%Y-%m-%d %H:%M:%S')
        appr_str = (order_time + timedelta(minutes=random.randint(5, 60))).strftime('%Y-%m-%d %H:%M:%S')

        # Review score based on delivery satisfaction
        if mode == "DELIVERY_DELAY" or order_status == "canceled":
            review_score = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        else:
            review_score = random.choices([5, 4, 3, 2, 1], weights=[0.65, 0.20, 0.08, 0.04, 0.03])[0]

        product_id = f"syn_prd_{random.randint(100, 999)}"
        seller_id = f"syn_sel_{random.randint(10, 50)}"
        freight_val = round(random.uniform(8.0, 32.0), 2)
        price_val = max(1.0, round(payment_val - freight_val, 2))
        payment_type = random.choice(self.PAYMENT_TYPES)
        review_id = f"syn_rev_{uuid.uuid4().hex[:12]}"

        return {
            "customer": (cust_id, unique_id, zip_prefix, city, state),
            "order": (order_id, cust_id, order_status, order_time_str, appr_str, carrier_str, cust_delivered_str, est_str),
            "payment": (order_id, 1, payment_type, 1, payment_val),
            "item": (order_id, 1, product_id, seller_id, est_str, price_val, freight_val),
            "review": (review_id, order_id, review_score, None, None, order_time_str, order_time_str),
            "payment_val": payment_val
        }

    def inject_batch(self, count: int = 10, mode: str = "NORMAL", notes: str = "") -> Dict[str, Any]:
        """
        Inject a batch of synthetic operational orders atomically into SQLite.
        """
        self.ensure_auxiliary_tables()
        orders_data = [self.generate_single_order(mode=mode) for _ in range(count)]
        total_val = sum(o["payment_val"] for o in orders_data)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")

            for o in orders_data:
                cursor.execute("""
                    INSERT OR REPLACE INTO olist_customers_dataset 
                    (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
                    VALUES (?, ?, ?, ?, ?)
                """, o["customer"])

                cursor.execute("""
                    INSERT OR REPLACE INTO olist_orders_dataset 
                    (order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at,
                     order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, o["order"])

                cursor.execute("""
                    INSERT OR REPLACE INTO olist_order_payments_dataset 
                    (order_id, payment_sequential, payment_type, payment_installments, payment_value)
                    VALUES (?, ?, ?, ?, ?)
                """, o["payment"])

                cursor.execute("""
                    INSERT OR REPLACE INTO olist_order_items_dataset 
                    (order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, o["item"])

                cursor.execute("""
                    INSERT OR REPLACE INTO olist_order_reviews_dataset 
                    (review_id, order_id, review_score, review_comment_title, review_comment_message,
                     review_creation_date, review_answer_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, o["review"])

            # Log to event log
            event_id = str(uuid.uuid4())
            now_iso = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO kpi_synthetic_event_log 
                (event_id, event_timestamp, scenario, orders_count, total_value, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (event_id, now_iso, mode, count, total_val, notes or f"Batch generated in {mode} mode"))
            
            conn.commit()

        with self._lock:
            self.stats["total_orders_injected"] += count
            self.stats["total_revenue_injected"] += total_val
            self.stats["last_injected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Synthetic Data Batch Injected: {count} orders, total ${total_val:.2f}, mode={mode}")
        return {
            "success": True,
            "orders_injected": count,
            "total_value": round(total_val, 2),
            "mode": mode,
            "timestamp": now_iso
        }

    def inject_churn_anomaly_cohort(self, churn_count: int = 150) -> Dict[str, Any]:
        """
        Inject a statistical cohort to deliberately spike the 30-day customer churn rate.
        Customers who purchased 31-60 days ago are not recorded purchasing in the last 30 days.
        """
        self.ensure_auxiliary_tables()
        today = datetime.now()
        ref_start = today - timedelta(days=58)
        ref_end = today - timedelta(days=32)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")

            for i in range(churn_count):
                cid = f"churn_{uuid.uuid4().hex[:10]}"
                cursor.execute("""
                    INSERT OR IGNORE INTO olist_customers_dataset 
                    (customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
                    VALUES (?, ?, '01000', 'sao paulo', 'SP')
                """, (cid, cid))

                past_time = ref_start + timedelta(days=random.randint(0, 20), hours=random.randint(8, 20))
                past_str = past_time.strftime('%Y-%m-%d %H:%M:%S')
                oid = f"chk_ord_{uuid.uuid4().hex[:10]}"

                cursor.execute("""
                    INSERT INTO olist_orders_dataset 
                    (order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at,
                     order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date)
                    VALUES (?, ?, 'delivered', ?, ?, ?, ?, ?)
                """, (oid, cid, past_str, past_str, past_str, past_str, past_str))

                cursor.execute("""
                    INSERT INTO olist_order_payments_dataset 
                    (order_id, payment_sequential, payment_type, payment_installments, payment_value)
                    VALUES (?, 1, 'credit_card', 1, ?)
                """, (oid, round(random.uniform(60, 180), 2)))

            conn.commit()

        logger.info(f"Injected churn cohort: {churn_count} past active customers not active in last 30 days.")
        return {
            "success": True,
            "scenario": "CHURN_SPIKE",
            "cohort_size": churn_count,
            "message": f"Successfully injected {churn_count} historical customers with zero 30-day retention to trigger Churn Alert."
        }

    def inject_data_quality_anomaly(self) -> Dict[str, Any]:
        """
        Inject deliberate edge-case dirty records to test Data Quality rule enforcement:
        - 1 record with NULL order status
        - 1 record with negative payment_value
        - 1 record with delivered date BEFORE purchase timestamp
        - 1 orphan payment without an order
        """
        self.ensure_auxiliary_tables()
        dirty_oid1 = f"dq_err_null_{uuid.uuid4().hex[:8]}"
        dirty_oid2 = f"dq_err_neg_{uuid.uuid4().hex[:8]}"
        dirty_oid3 = f"dq_err_time_{uuid.uuid4().hex[:8]}"
        orphan_oid = f"dq_err_orph_{uuid.uuid4().hex[:8]}"

        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        earlier_str = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")

            # 1. Null status
            cursor.execute("""
                INSERT INTO olist_orders_dataset 
                (order_id, customer_id, order_status, order_purchase_timestamp)
                VALUES (?, 'test_cst', NULL, ?)
            """, (dirty_oid1, now_str))

            # 2. Negative payment
            cursor.execute("""
                INSERT INTO olist_orders_dataset 
                (order_id, customer_id, order_status, order_purchase_timestamp)
                VALUES (?, 'test_cst', 'delivered', ?)
            """, (dirty_oid2, now_str))
            cursor.execute("""
                INSERT INTO olist_order_payments_dataset 
                (order_id, payment_sequential, payment_type, payment_installments, payment_value)
                VALUES (?, 1, 'credit_card', 1, -95.50)
            """, (dirty_oid2,))

            # 3. Time paradox (delivered before purchased)
            cursor.execute("""
                INSERT INTO olist_orders_dataset 
                (order_id, customer_id, order_status, order_purchase_timestamp, order_delivered_customer_date)
                VALUES (?, 'test_cst', 'delivered', ?, ?)
            """, (dirty_oid3, now_str, earlier_str))

            # 4. Orphan payment
            cursor.execute("""
                INSERT INTO olist_order_payments_dataset 
                (order_id, payment_sequential, payment_type, payment_installments, payment_value)
                VALUES (?, 1, 'credit_card', 1, 150.00)
            """, (orphan_oid,))

            conn.commit()

        logger.info("Injected dirty test records for Data Quality audit.")
        return {
            "success": True,
            "scenario": "DATA_QUALITY_ANOMALY",
            "message": "Injected 4 controlled data defects (NULL status, negative payment, delivery date paradox, orphan payment)."
        }

    def start_realtime_stream(self, interval_seconds: float = 5.0, mode: str = "NORMAL"):
        """Start background streaming thread generating continuous orders."""
        if self.is_streaming:
            self.stream_mode = mode
            self.stream_interval = interval_seconds
            return

        self.is_streaming = True
        self.stream_interval = max(1.0, float(interval_seconds))
        self.stream_mode = mode
        self.stats["stream_started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.stats["active_mode"] = mode

        def _stream_worker():
            logger.info(f"Real-time synthetic stream started (Interval: {self.stream_interval}s, Mode: {self.stream_mode})")
            while self.is_streaming:
                try:
                    # Generate 1 to 3 orders per tick
                    batch_size = random.randint(1, 3)
                    self.inject_batch(count=batch_size, mode=self.stream_mode, notes="Real-time Stream Event")
                except Exception as e:
                    logger.error(f"Error in synthetic stream worker: {e}")
                time.sleep(self.stream_interval)
            logger.info("Real-time synthetic stream worker terminated.")

        self.stream_thread = threading.Thread(target=_stream_worker, daemon=True)
        self.stream_thread.start()

    def stop_realtime_stream(self):
        """Stop background streaming thread."""
        self.is_streaming = False
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=3.0)
        self.stream_thread = None
        self.stats["active_mode"] = "PAUSED"
        logger.info("Real-time synthetic stream stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Return streaming generator status and metrics."""
        return {
            "is_streaming": self.is_streaming,
            "interval_seconds": self.stream_interval,
            "stream_mode": self.stream_mode,
            "total_orders_injected": self.stats["total_orders_injected"],
            "total_revenue_injected": round(self.stats["total_revenue_injected"], 2),
            "last_injected_at": self.stats["last_injected_at"],
            "stream_started_at": self.stats["stream_started_at"],
            "active_mode": self.stream_mode if self.is_streaming else "PAUSED"
        }

# Global singleton instance
generator = RealtimeSyntheticGenerator()
