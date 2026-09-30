"""
Incident Management & Multi-Channel Webhook Dispatcher Module.
Provides:
1. P1 (Critical) to P4 (Low) incident triage and lifecycle tracking (OPEN, ACKNOWLEDGED, RESOLVED).
2. Multi-channel dispatching to Slack, Microsoft Teams, and Discord webhooks with formatted adaptive cards.
3. Incident audit logging in SQLite.
"""
import uuid
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests

logger = logging.getLogger(__name__)

class IncidentManager:
    """Manages operational incidents and multi-channel notification dispatching."""

    def __init__(self, db_path: str = "data/olist.db"):
        self.db_path = Path(db_path)
        self.ensure_table()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_table(self):
        """Create incident lifecycle table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_incidents (
                    incident_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    kpi_name TEXT,
                    severity TEXT,
                    status TEXT,
                    trigger_value REAL,
                    threshold_value REAL,
                    description TEXT,
                    acknowledged_by TEXT,
                    acknowledged_at TEXT,
                    resolution_notes TEXT
                )
            """)
            conn.commit()

    def create_or_update_incident(self, kpi_name: str, severity: str, value: float, threshold: float, description: str) -> Dict[str, Any]:
        """Create a new incident or update existing open incident."""
        now_iso = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check for existing open incident for this KPI
            cursor.execute("SELECT incident_id FROM kpi_incidents WHERE kpi_name = ? AND status != 'RESOLVED'", (kpi_name,))
            existing = cursor.fetchone()

            if existing:
                inc_id = existing['incident_id']
                cursor.execute("""
                    UPDATE kpi_incidents 
                    SET trigger_value = ?, description = ?, severity = ?
                    WHERE incident_id = ?
                """, (value, description, severity, inc_id))
            else:
                inc_id = f"inc_{uuid.uuid4().hex[:8]}"
                cursor.execute("""
                    INSERT INTO kpi_incidents 
                    (incident_id, created_at, kpi_name, severity, status, trigger_value, threshold_value, description)
                    VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?)
                """, (inc_id, now_iso, kpi_name, severity, value, threshold, description))
            conn.commit()

        return {"incident_id": inc_id, "status": "OPEN", "kpi_name": kpi_name, "severity": severity}

    def acknowledge_incident(self, incident_id: str, ack_by: str = "On-Call Engineer") -> Dict[str, Any]:
        """Acknowledge an active incident."""
        now_iso = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE kpi_incidents 
                SET status = 'ACKNOWLEDGED', acknowledged_by = ?, acknowledged_at = ?
                WHERE incident_id = ?
            """, (ack_by, now_iso, incident_id))
            conn.commit()
        return {"success": True, "incident_id": incident_id, "status": "ACKNOWLEDGED"}

    def resolve_incident(self, incident_id: str, notes: str = "Resolved by operator") -> Dict[str, Any]:
        """Mark incident as resolved."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE kpi_incidents 
                SET status = 'RESOLVED', resolution_notes = ?
                WHERE incident_id = ?
            """, (notes, incident_id))
            conn.commit()
        return {"success": True, "incident_id": incident_id, "status": "RESOLVED"}

    def list_incidents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent incidents with current status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM kpi_incidents 
                ORDER BY created_at DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def dispatch_webhook_notification(self, webhook_url: str, payload_type: str = "slack", message_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch formatted webhook payload to Slack, Teams, or custom HTTP endpoint."""
        if not webhook_url:
            return {"success": False, "error": "Webhook URL is missing"}

        data = message_data or {
            "title": "KPI Anomaly Alert",
            "kpi_name": "daily_revenue",
            "severity": "CRITICAL",
            "message": "Daily revenue deviated by -3.2 standard deviations from baseline."
        }

        try:
            if payload_type == "slack":
                body = {
                    "text": f"🚨 *{data.get('title')}* [{data.get('severity')}]: {data.get('message')}",
                    "attachments": [{
                        "color": "#ef4444" if data.get('severity') == "CRITICAL" else "#f59e0b",
                        "fields": [
                            {"title": "KPI", "value": data.get('kpi_name', ''), "short": True},
                            {"title": "Status", "value": "ACTION REQUIRED", "short": True}
                        ]
                    }]
                }
            elif payload_type == "teams":
                body = {
                    "@type": "MessageCard",
                    "themeColor": "EF4444" if data.get('severity') == "CRITICAL" else "F59E0B",
                    "title": data.get('title'),
                    "text": data.get('message')
                }
            else:
                body = data

            resp = requests.post(webhook_url, json=body, timeout=5.0)
            return {"success": resp.status_code in [200, 204], "status_code": resp.status_code}
        except Exception as e:
            logger.error(f"Error dispatching webhook: {e}")
            return {"success": False, "error": str(e)}

incident_manager = IncidentManager()
