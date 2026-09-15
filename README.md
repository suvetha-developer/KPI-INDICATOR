# Automated KPI Monitoring & Alert System for Olist Dataset

A comprehensive system for automatically tracking KPIs, detecting anomalies, and sending alerts via email/Slack with Excel reporting.

## Features

- **Automated KPI Tracking**: Monitors 9 key e-commerce KPIs from Olist dataset
- **Anomaly Detection**: Multiple detection methods (percentage drop/spike, statistical)
- **Multi-channel Alerts**: Email and Slack notifications
- **Excel Reports**: Automated daily reports with charts and color-coded status
- **SQLite Database**: Simple, file-based database (no server setup required)

## Project Structure

```
kpi-indicator/
├── main.py                 # Main orchestrator script
├── requirements.txt        # Python dependencies
├── config/
│   └── kpi_config.json     # KPI definitions and alert settings
├── src/
│   ├── database.py         # Database connection handler
│   ├── data_loader.py      # CSV to database loader
│   ├── kpi_calculator.py   # KPI calculation & anomaly detection
│   ├── alert_sender.py     # Email/Slack alert sender
│   └── excel_reporter.py   # Excel report generator
├── scripts/
│   └── setup_database.py   # Initial data loading script
├── data/                   # Place Olist CSV files here
├── logs/                   # Log files (auto-created)
└── reports/                # Excel reports (auto-created)
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Olist Dataset

Place all Olist CSV files in the `data/` directory. Required files:
- `olist_customers_dataset.csv`
- `olist_geolocation_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `product_category_name_translation.csv`

### 3. Load Data into Database

Run the setup script to load CSV files into SQLite database:

```bash
python scripts/setup_database.py
```

This will:
- Create database schema
- Load all CSV files
- Create indexes for performance
- Verify data was loaded correctly

### 4. Configure Alerts (Optional)

Edit `config/kpi_config.json` to configure email/Slack alerts:

**Email Configuration:**
```json
"email": {
  "enabled": true,
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "your_email@gmail.com",
  "smtp_password": "your_app_password",
  "recipients": ["analyst@company.com"]
}
```

**Slack Configuration:**
```json
"slack": {
  "enabled": true,
  "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
  "channel": "#kpi-alerts"
}
```

## Usage

### Run KPI Monitoring

```bash
python main.py
```

This will:
1. Calculate all configured KPIs
2. Detect anomalies
3. Send alerts (if configured and anomalies detected)
4. Generate Excel report in `reports/` directory

### Schedule Automated Runs

**Windows Task Scheduler:**
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., Daily at 9:00 AM)
4. Action: Start a program
5. Program: `python.exe`
6. Arguments: `C:\path\to\main.py`
7. Start in: `C:\path\to\kpi-indicator`

## Monitored KPIs

1. **Daily Revenue** - Total revenue from orders (alert if drops >10%)
2. **Average Order Value (AOV)** - Average payment value per order
3. **Daily Order Volume** - Number of orders per day
4. **Customer Churn Rate** - Percentage of customers who stopped ordering
5. **Conversion Rate** - Percentage of orders that were delivered
6. **Payment Approval Rate** - Percentage of orders approved/processing
7. **Average Delivery Time** - Average days to deliver orders
8. **On-Time Delivery Rate** - Percentage of orders delivered on time
9. **Repeat Customer Rate** - Percentage of customers with multiple orders

## Output Files

- **Logs**: `logs/kpi_monitor_YYYYMMDD.log` - Daily log files
- **Reports**: `reports/kpi_report_YYYYMMDD_HHMMSS.xlsx` - Excel reports with:
  - KPI Summary sheet (color-coded status)
  - Summary Statistics sheet
  - Charts sheet (visualizations)

## Configuration

### KPI Thresholds

Edit `config/kpi_config.json` to customize:
- Threshold values (percentage/absolute)
- Comparison periods (previous_week, previous_month)
- Alert priorities (high, medium, low)
- Enable/disable specific KPIs

### SQL Queries

Each KPI has a custom SQL query. Modify queries in `config/kpi_config.json` to:
- Change date ranges
- Add filters
- Calculate different metrics

## Troubleshooting

**Database not found:**
- Run `python scripts/setup_database.py` first

**No data in KPIs:**
- Check if CSV files are in `data/` directory
- Verify CSV file names match expected names
- Check database: `data/olist.db` exists and has data

**Alerts not sending:**
- Verify email/Slack configuration in `config/kpi_config.json`
- Check logs for error messages
- Test email credentials separately

**SQL Query Errors:**
- Check SQLite date functions (SQLite uses different syntax than PostgreSQL)
- Verify table names match loaded data
- Check logs for specific error messages

## Exit Codes

- `0`: All KPIs normal
- `1`: Errors detected
- `2`: Alerts detected (but no errors)

Useful for scheduling scripts to handle different outcomes.

## Next Steps

1. Load your Olist dataset using `scripts/setup_database.py`
2. Run `python main.py` to test the system
3. Configure alerts if needed
4. Schedule automated runs
5. Review Excel reports and adjust thresholds as needed

