# KPI Dashboard - Quick Start Guide

## 🚀 Starting the Dashboard

Run the following command in your terminal:

```bash
python dashboard.py
```

The dashboard will start on: **http://localhost:5000**

Open your web browser and navigate to that URL to see the real-time KPI monitoring dashboard.

## 📊 Dashboard Features

### Real-time KPI Cards
- **9 KPI Cards** showing current values, status, and trends
- **Color-coded status**: Green (Normal), Red (Alert), Orange (Error)
- **Trend indicators**: Shows percentage change vs baseline

### Status Bar
- Total KPIs monitored
- Alert count
- Normal count
- Last update timestamp

### Revenue Trend Chart
- Visual representation of revenue metrics
- Compares current vs baseline values

### Live Anomalies Panel
- Real-time list of detected anomalies
- Shows KPI name, description, value, and change percentage
- Timestamp for each anomaly

### Auto-refresh
- Dashboard automatically refreshes every 30 seconds
- Manual refresh button available

## 🔧 API Endpoints

The dashboard provides REST API endpoints:

- `GET /` - Main dashboard page
- `GET /api/kpis` - Get all current KPI values
- `GET /api/refresh` - Force refresh of KPIs
- `GET /api/status` - Get system status

## 🛑 Stopping the Dashboard

Press `Ctrl+C` in the terminal where the dashboard is running.

## 📝 Notes

- The dashboard connects to the same database as the main monitoring system
- KPIs are calculated in real-time when you access the dashboard
- All 9 configured KPIs are displayed
- Anomalies are highlighted in red with detailed information

## 🎨 Customization

To customize the dashboard:
- Edit `templates/dashboard.html` for UI changes
- Modify `dashboard.py` for API changes
- Adjust refresh interval in the JavaScript (currently 30 seconds)

Enjoy your real-time KPI monitoring! 🎉

