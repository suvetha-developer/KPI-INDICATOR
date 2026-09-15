# KPI Monitoring System - Deployment Guide

This guide explains how to set up, run, and maintain the KPI Monitoring System.

## Quick Start

We have provided batch scripts for easy execution on Windows:

1.  **Setup**: Run `setup.bat` once to install dependencies and initialize the database.
    -   *Note: If you already have the data locally and the database is set up, you can skip this.*
2.  **Dashboard**: Run `run_dashboard.bat` to launch the real-time KPI dashboard.
    -   This will open [http://localhost:5000](http://localhost:5000) in your default browser.
3.  **Monitor**: Run `run_monitor.bat` to perform a single check of all KPIs, generate an Excel report, and send alerts (if configured).

## Deployment Options

### 1. Local Deployment (Interactive)

Use the batch scripts mentioned above. Keep `run_dashboard.bat` running to access the web interface.

### 2. Scheduled Monitoring (Background)

To run the monitoring logic periodically (e.g., daily at 9 AM) without user intervention:

1.  Open **Windows Task Scheduler**.
2.  Select **Create Basic Task**.
3.  Name it "KPI Monitor Daily Run".
4.  Trigger: **Daily**, set time to **09:00:00**.
5.  Action: **Start a program**.
6.  Program/script: Browse to `run_monitor.bat` in this folder.
7.  Start in: Enter the full path to this directory (e.g., `C:\Users\Swetha\Desktop\kpi indicator`).

### 3. Dedicated Dashboard Server

If running on a dedicated server or cloud VM:

1.  Ensure Python 3.8+ is installed.
2.  Copy all files to the server.
3.  Run `pip install -r requirements.txt`.
4.  Run `python scripts/setup_database.py`.
5.  Run `python dashboard.py`.
    -   *Recommendation*: Use a production WSGI server like `gunicorn` (Linux) or `waitress` (Windows) instead of the default development server.
    -   Example with Waitress: `pip install waitress` then `waitress-serve --port=5000 dashboard:app`

## Troubleshooting

-   **Database Errors**: Run `setup.bat` to ensure the database is correctly initialized containing all CSV data.
-   **Missing Dependencies**: Ensure `pip install -r requirements.txt` ran successfully.
-   **Port in Use**: If the dashboard fails to start, check if port 5000 is occupied. You can change the port in `dashboard.py`.
