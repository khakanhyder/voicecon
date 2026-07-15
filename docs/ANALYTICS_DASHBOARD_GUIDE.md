# Analytics Dashboard Guide

## Overview

The Analytics Dashboard provides comprehensive real-time and historical insights into your Voicecon platform's performance. It includes interactive visualizations, exportable reports, and auto-refreshing metrics.

## Features

### 1. Real-Time Monitoring
- Live system health status
- Active calls counter
- Calls per hour tracking
- Average response time
- Error rate monitoring
- Active agents and integrations count

### 2. Key Performance Indicators (KPIs)
- **Total Calls**: Daily call volume with trend indicators
- **Average Duration**: Call duration metrics with trends
- **Active Agents**: Number of operational AI agents
- **Total Cost**: Daily spending with cost trends

### 3. Interactive Visualizations
- **Call Analytics**: Volume trends, duration analysis, outcome distribution
- **Agent Performance**: Per-agent metrics, sentiment analysis, rankings
- **Integration Health**: Health scores, response times, uptime tracking
- **Cost Breakdown**: Service-wise costs, trends, optimization tips

### 4. Export Capabilities
- CSV export for data analysis
- PDF export for reports and presentations
- Customizable date ranges
- Multiple report types

### 5. Auto-Refresh
- Configurable auto-refresh (60-second intervals)
- Manual refresh option
- Real-time data updates

## Dashboard Sections

### System Health Banner

Located at the top of the dashboard, this banner provides instant system status:

```
Status Indicators:
- Healthy: Green - All systems operational
- Degraded: Yellow - Some performance issues
- Down: Red - Critical system failures
```

**Metrics Displayed:**
- Active Calls (currently in progress)
- Calls/Hour (last 60 minutes)
- Avg Response Time (milliseconds)
- Error Rate (percentage)

### Key Metrics Cards

Four prominent cards display the most important daily metrics:

#### 1. Total Calls Card
- **Icon**: Phone
- **Metrics**:
  - Total calls today
  - Success rate
  - Trend percentage vs. yesterday
- **Color**: Blue

#### 2. Average Duration Card
- **Icon**: Lightning bolt (Zap)
- **Metrics**:
  - Average call duration
  - Total duration
  - Trend percentage
- **Color**: Purple

#### 3. Active Agents Card
- **Icon**: Users
- **Metrics**:
  - Number of active agents
  - Active integrations count
- **Color**: Green

#### 4. Total Cost Card
- **Icon**: Dollar sign
- **Metrics**:
  - Total cost today
  - Cost per call
  - Cost trend percentage
- **Color**: Yellow

### Call Analytics Section

Comprehensive call performance analysis with three tabs:

#### Call Volume Tab
**Visualizations:**
1. **Summary Stats**: Total calls, completed, failed, success rate
2. **Line Chart**: Call volume trend over time
   - Total calls line
   - Completed calls line
   - Failed calls line
3. **Bar Chart**: Hourly call distribution

**Key Insights:**
- Peak calling hours
- Success/failure patterns
- Daily trends

#### Duration Tab
**Visualizations:**
1. **Summary Stats**: Average, min, and max durations
2. **Line Chart**: Duration trends
   - Average duration
   - Maximum duration (dashed)
   - Minimum duration (dashed)

**Key Insights:**
- Call length patterns
- Duration consistency
- Outliers identification

#### Outcomes Tab
**Visualizations:**
1. **Pie Chart**: Outcome distribution
   - Completed (green)
   - Failed (red)
   - Abandoned (yellow)
   - Transferred (blue)
2. **Outcome Breakdown**: Detailed statistics
3. **Success Rate Indicator**: Visual progress bar

**Key Insights:**
- Call resolution rates
- Failure analysis
- Transfer patterns

### Agent Performance Section

Detailed analysis of individual AI agent performance:

#### Agent Overview Cards
- **Display**: Grid of agent cards
- **Click to Expand**: Shows detailed metrics
- **Top Performer Badge**: Gold award icon for best performer

**Per-Agent Metrics:**
- Total calls handled
- Success rate percentage
- Sentiment analysis (Positive/Neutral/Negative)
- Response time
- Function calls made
- Token usage

#### Selected Agent Details
When clicking an agent card, displays:
- 6 detailed metric cards
- Radar chart showing performance profile across 5 dimensions:
  - Call Volume
  - Sentiment
  - Success Rate
  - Response Time
  - Function Usage

#### Comparison Charts
1. **Call Volume by Agent**: Horizontal bar chart
2. **Success Rate by Agent**: Vertical bar chart
3. **Sentiment Trend**: Line chart for top 3 agents over time

#### Agent Rankings Table
Sortable table showing:
- Rank (with top performer badge)
- Agent name with avatar
- Total calls
- Success rate
- Average sentiment
- Response time

### Integration Health Section

Monitors all connected third-party integrations:

#### Integration Status Cards
Each integration displays:
- **Icon**: Integration logo/emoji
- **Status Badge**: Healthy/Degraded/Down
- **Metrics**:
  - Total executions
  - Success rate
  - Average response time
  - Error count
  - Health score (0-100)
  - Uptime percentage

**Health Score Indicators:**
- 95-100: Green (Excellent)
- 85-94: Yellow (Good)
- Below 85: Red (Needs attention)

#### Health Trend Chart
Line chart showing health scores over time for top integrations.

#### Response Time Comparison
Horizontal bar chart comparing average response times across all integrations.

**Color Coding:**
- ≤200ms: Green (Fast)
- 201-300ms: Blue (Medium)
- 301-400ms: Yellow (Slow)
- >400ms: Red (Very Slow)

#### Summary Statistics
Three cards showing:
1. Healthy integrations count
2. Total executions across all integrations
3. Average health score

### Cost Breakdown Section

Financial analysis and cost optimization:

#### Cost Summary Cards
- **Total Cost**: Current period spending with trend
- **Cost Per Call**: Average cost per call and per minute

#### Cost Distribution
1. **Pie Chart**: Service-wise cost breakdown
   - LLM (GPT-4)
   - Telephony
   - Text-to-Speech
   - Speech-to-Text
2. **Detailed List**: Exact amounts and percentages

#### Cost Trends
Line chart showing:
- Total cost trend
- LLM cost trend (dashed)
- Telephony cost trend (dashed)

#### Cost by Agent
Bar chart showing total cost per agent.

#### Optimization Tips
Automated suggestions for cost reduction:
- Model optimization recommendations
- Prompt engineering tips
- Caching strategies

## Date Range Filtering

The date range picker allows filtering all dashboard data:

**Features:**
- Start date selector
- End date selector
- Applies to all charts and metrics
- Default: Last 7 days

**Usage:**
```
1. Click on start date input
2. Select desired start date
3. Click on end date input
4. Select desired end date
5. Data automatically updates
```

## Auto-Refresh

**Default Behavior:**
- Auto-refresh: ON
- Interval: 60 seconds
- Updates real-time metrics only

**Toggle:**
- Click "Auto Refresh On/Off" button
- Icon shows spinning animation during refresh

**Manual Refresh:**
- Always available even when auto-refresh is off
- Click button to refresh immediately

## Export Functionality

### CSV Export

**What Gets Exported:**
- Dashboard summary with key metrics
- Date range information
- Generation timestamp
- All numerical values

**File Format:**
```csv
Analytics Dashboard Summary
Date Range: 2024-01-10 to 2024-01-16
Generated: 2024-01-16 14:30:25

Metric,Value,Change,Status
Total Calls,342,+12.5%,Up
Average Duration,2m 30s,-3.2%,Down
...
```

**Filename:**
`analytics_dashboard_summary_20240116.csv`

### PDF Export

**What Gets Exported:**
- Formatted HTML report
- Dashboard summary table
- Professional styling
- Date range and metadata
- Company branding footer

**Process:**
1. Click "Export" → "Export PDF"
2. New window opens with formatted report
3. Browser print dialog appears
4. Save as PDF using browser's print function

**Use Cases:**
- Executive reports
- Client presentations
- Compliance documentation
- Historical records

## API Integration

### Fetching Dashboard Data

```typescript
const fetchDashboardData = async () => {
  const response = await fetch('/api/analytics/dashboard');
  const data = await response.json();

  setDashboardData({
    realtime: data.realtime,
    today: data.today,
  });
};
```

### Expected API Response

```json
{
  "realtime": {
    "activeCalls": 3,
    "callsLastHour": 42,
    "callsLast5Min": 7,
    "avgResponseTime": 245,
    "errorRate": 1.2,
    "systemHealth": "healthy",
    "activeAgents": 8,
    "activeIntegrations": 5
  },
  "today": {
    "totalCalls": 342,
    "totalDuration": 51300,
    "avgDuration": 150,
    "successRate": 94.5,
    "totalCost": 127.50,
    "callsTrend": 12.5,
    "durationTrend": -3.2,
    "costTrend": 8.7
  }
}
```

## Component Structure

### Main Dashboard Component
**File**: `frontend/src/app/(dashboard)/analytics/page.tsx`

**State Management:**
```typescript
- dateRange: { start: string, end: string }
- dashboardData: DashboardData
- isRefreshing: boolean
- autoRefresh: boolean
```

**Child Components:**
- CallMetrics
- AgentPerformance
- IntegrationHealth
- CostBreakdown

### CallMetrics Component
**File**: `frontend/src/components/analytics/CallMetrics.tsx`

**Features:**
- Tab navigation (Volume/Duration/Outcomes)
- Multiple chart types (Line, Bar, Pie)
- Summary statistics
- Interactive tooltips

### AgentPerformance Component
**File**: `frontend/src/components/analytics/AgentPerformance.tsx`

**Features:**
- Agent cards with selection
- Radar chart for performance profile
- Comparison charts
- Rankings table
- Top performer badge

### IntegrationHealth Component
**File**: `frontend/src/components/analytics/IntegrationHealth.tsx`

**Features:**
- Status indicators
- Health score visualization
- Trend analysis
- Response time comparison
- Summary statistics

### CostBreakdown Component
**File**: `frontend/src/components/analytics/CostBreakdown.tsx`

**Features:**
- Pie chart distribution
- Cost trends
- Agent-wise breakdown
- Optimization recommendations
- Service type legends

## Recharts Integration

All visualizations use Recharts library for consistency and performance.

### Common Chart Configuration

```typescript
<ResponsiveContainer width="100%" height={300}>
  <LineChart data={data}>
    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
    <XAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
    <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} />
    <Tooltip content={<CustomTooltip />} />
    <Legend />
    <Line dataKey="value" stroke="#3b82f6" strokeWidth={2} />
  </LineChart>
</ResponsiveContainer>
```

### Custom Tooltips

All charts include custom-styled tooltips:
- White background
- Border and shadow
- Formatted values
- Color-coded indicators

### Color Palette

Consistent colors across all charts:
- **Primary**: `#6366f1` (Indigo)
- **Success**: `#10b981` (Green)
- **Warning**: `#f59e0b` (Yellow)
- **Error**: `#ef4444` (Red)
- **Info**: `#3b82f6` (Blue)
- **Purple**: `#8b5cf6`

## Responsive Design

The dashboard is fully responsive across all screen sizes:

### Desktop (1280px+)
- 4-column KPI cards
- Side-by-side comparison charts
- Full-width tables

### Tablet (768px - 1279px)
- 2-column KPI cards
- Stacked comparison charts
- Scrollable tables

### Mobile (< 768px)
- Single column layout
- Stacked KPI cards
- Horizontal scroll for wide tables
- Collapsible sections

## Performance Optimization

### Data Loading
- Lazy load chart components
- Pagination for large datasets
- Efficient re-rendering

### Chart Rendering
- Use `ResponsiveContainer` for adaptive sizing
- Limit data points for better performance
- Debounce resize events

### Auto-Refresh
- Only fetch changed data
- Incremental updates
- Efficient state management

## Best Practices

### 1. Date Range Selection
- Default to last 7 days for balance
- Limit to 90 days max to prevent performance issues
- Provide quick presets (Today, Last 7 days, Last 30 days)

### 2. Export Usage
- Export during off-peak hours for large datasets
- Use CSV for data analysis
- Use PDF for presentations

### 3. Monitoring
- Check system health banner regularly
- Set up alerts for degraded status
- Review cost trends weekly

### 4. Agent Optimization
- Monitor low-performing agents
- Review sentiment trends
- Optimize based on token usage

### 5. Integration Management
- Address integrations with health score < 90
- Monitor response times
- Review error patterns

## Troubleshooting

### Charts Not Loading
**Symptoms:** Blank chart areas
**Solutions:**
1. Check browser console for errors
2. Verify data format matches expected schema
3. Ensure Recharts is properly installed
4. Check for JavaScript errors

### Data Not Updating
**Symptoms:** Stale data despite auto-refresh
**Solutions:**
1. Check network tab for API errors
2. Verify auto-refresh is enabled
3. Check API endpoint availability
4. Review browser console for errors

### Export Not Working
**Symptoms:** Export button doesn't respond
**Solutions:**
1. Allow popups for PDF export
2. Check browser's download settings
3. Verify export functions are imported
4. Test with smaller date ranges

### Slow Performance
**Symptoms:** Dashboard loads slowly
**Solutions:**
1. Reduce date range
2. Disable auto-refresh temporarily
3. Clear browser cache
4. Check network speed
5. Review backend query optimization

## Future Enhancements

### Planned Features
1. **Custom Dashboards**: User-configurable widget layout
2. **Scheduled Reports**: Email reports on schedule
3. **Alerts & Notifications**: Threshold-based alerting
4. **Drill-Down Analysis**: Click charts to see detailed data
5. **Comparison Mode**: Compare multiple time periods
6. **Saved Filters**: Save commonly used date ranges
7. **Data Export API**: Programmatic data access
8. **Real-Time Streaming**: WebSocket-based live updates

### Advanced Visualizations
1. Heatmaps for call patterns
2. Geographic distribution maps
3. Funnel charts for conversion tracking
4. Sankey diagrams for call flow
5. Gauge charts for KPIs

## Summary

The Analytics Dashboard provides:

✅ **Comprehensive Metrics** - All key performance indicators in one place
✅ **Real-Time Monitoring** - Live system status and active metrics
✅ **Interactive Visualizations** - Beautiful, responsive charts
✅ **Export Capabilities** - CSV and PDF export functionality
✅ **Agent Insights** - Per-agent performance analysis
✅ **Cost Analysis** - Detailed spending breakdown
✅ **Integration Monitoring** - Third-party service health
✅ **Auto-Refresh** - Always up-to-date data
✅ **Responsive Design** - Works on all devices
✅ **Production Ready** - Optimized and tested

For backend analytics details, see [ANALYTICS_SYSTEM_GUIDE.md](ANALYTICS_SYSTEM_GUIDE.md).
For scheduler information, see [ANALYTICS_SCHEDULER_GUIDE.md](ANALYTICS_SCHEDULER_GUIDE.md).
