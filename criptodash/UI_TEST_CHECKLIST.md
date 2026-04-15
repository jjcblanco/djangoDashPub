# New UI Features - Test Checklist

This checklist covers all new whale tracking UI features implemented in the recent update. Use this to verify everything works correctly in production.

## Test Environment
- [ ] **URL**: `https://your-domain.com/dashboard/whale-insights/`
- [ ] **Browser**: Chrome/Firefox latest
- [ ] **Login**: Ensure you're logged in as admin/user with permissions

## 1. Overview Tab

### 1.1 Dashboard Metrics
- [ ] **Total Wallets** card displays correct count
- [ ] **Active Today** shows wallets with recent activity
- [ ] **Total Balance** shows aggregated balance (if available)
- [ ] **Signals Found** shows consensus signals count
- [ ] **Last Sync** shows timestamp of most recent sync
- [ ] **Refresh button** updates metrics without page reload

### 1.2 Performance Charts
- [ ] **Wallet Growth Chart** shows historical wallet count
- [ ] **Transaction Volume Chart** shows 7-day transaction trend
- [ ] **Chain Distribution Chart** shows pie chart of wallets by blockchain
- [ ] **Charts respond to mouse hover** showing tooltips
- [ ] **Time filters** (7d, 30d, 90d) update charts

### 1.3 Recent Activity
- [ ] **Latest Transactions** table shows 10 most recent transactions
- [ ] **Transaction details** show type, amount, timestamp
- [ ] **Wallet links** navigate to wallet detail
- [ ] **"View All" button** navigates to Wallets tab

## 2. Wallets Tab

### 2.1 Wallet List
- [ ] **Table displays all wallets** with pagination
- [ ] **Columns**: Address, Blockchain, Status, Last Sync, Balance, Score
- [ ] **Sorting works** for each column (click headers)
- [ ] **Search box filters** wallets by address
- [ ] **Blockchain filter** dropdown filters by chain
- [ ] **Status filter** shows IDLE/SYNCING/ERROR wallets

### 2.2 Individual Wallet Actions
- [ ] **"Sync Now" button** triggers immediate sync (check Celery logs)
- [ ] **"View Transactions"** navigates to transaction history
- [ ] **"Edit" button** opens edit modal (if implemented)
- [ ] **"Delete" button** with confirmation

### 2.3 Bulk Operations
- [ ] **"Bulk Import" button** opens import modal
- [ ] **Modal accepts wallet addresses** (one per line)
- [ ] **Blockchain selection** in modal
- [ ] **Import progress** shows during processing
- [ ] **Success notification** appears after import
- [ ] **Imported wallets appear** in list immediately
- [ ] **Telegram notification sent** (check bot messages)

### 2.4 Wallet Details
- [ ] **Click wallet address** navigates to detailed view
- [ ] **Detail view shows**: Transactions, Holdings, History
- [ ] **"Back to list"** navigation works

## 3. Patterns Tab

### 3.1 Pattern Detection
- [ ] **Pattern list displays** detected whale patterns
- [ ] **Pattern types**: Large transfers, Accumulation, Distribution, etc.
- [ ] **Each pattern shows**: Description, Confidence, Wallets involved
- [ ] **Pattern timeline visualization** (if implemented)

### 3.2 Pattern Analysis
- [ ] **"Analyze Pattern" button** shows detailed analysis
- [ ] **Historical pattern frequency** chart
- [ ] **Cross-chain pattern detection** (if applicable)

## 4. Discovery Tab

### 4.1 Consensus Signals
- [ ] **"AI-Powered Discovery" section visible**
- [ ] **Consensus signals list displays** with scores
- [ ] **Each signal shows**: Type, Confidence, Blockchain, Timestamp
- [ ] **Signal details expand** on click
- [ ] **"Add to Hunt" button** adds signal to hunting targets

### 4.2 Discovery Controls
- [ ] **"Run Discovery Scan" button** triggers new scan
- [ ] **Scan progress indicator** appears
- [ ] **Results refresh** automatically after scan
- [ ] **Discovery settings** (if available) allow configuration

### 4.3 Signal Types
- [ ] **Large accumulation patterns** detected
- [ ] **Cross-chain movements** detected
- [ ] **New whale identification** works
- [ ] **Market correlation signals** (if implemented)

## 5. Hunting Tab

### 5.1 Hunting Dashboard
- [ ] **Active targets counter** displays
- [ ] **Success rate metric** shows
- [ ] **Recent hunts timeline** (if implemented)

### 5.2 Advanced Filters
- [ ] **Min Score slider** filters targets by score (0-100)
- [ ] **Blockchain multi-select** filters by chains
- [ ] **Timeframe dropdown** (24h, 7d, 30d, All)
- [ ] **Status filter** (Active, Completed, Archived)
- [ ] **"Apply Filters" button** updates target list
- [ ] **Filters persist** between page reloads (localStorage)
- [ ] **"Reset Filters" button** clears all filters

### 5.3 Target List
- [ ] **Targets table displays** filtered results
- [ ] **Columns**: Address, Score, Blockchain, Signal, Added, Status
- [ ] **"Add to Watchlist" button** adds target to monitoring
- [ ] **"Ignore" button** archives target
- [ ] **"View Details"** shows full target analysis

### 5.4 Automated Hunting
- [ ] **"Enable Auto-hunt" toggle** (if implemented)
- [ ] **Auto-hunt settings** allow configuration
- [ ] **Scheduled hunts run** every 6 hours (check Celery logs)

## 6. Responsive Design

### 6.1 Desktop (≥1024px)
- [ ] **All 5 tabs visible** in horizontal layout
- [ ] **Tables show all columns**
- [ ] **Charts full width**

### 6.2 Tablet (768px-1023px)
- [ ] **Tab navigation adapts** (still horizontal)
- [ ] **Tables may have horizontal scroll**
- [ ] **Charts resize appropriately**

### 6.3 Mobile (<768px)
- [ ] **Tab navigation becomes** vertical/accordion
- [ ] **Tables become card views** or scroll horizontally
- [ ] **Charts remain readable**
- [ ] **Buttons have adequate touch targets**
- [ ] **No horizontal scrolling** on main layout

## 7. Real-time Features

### 7.1 WebSocket Connection
- [ ] **Browser console shows** WebSocket connection established
- [ ] **Connection status indicator** (if implemented)
- [ ] **Automatic reconnection** on disconnect

### 7.2 Live Updates
- [ ] **New transactions appear** without page refresh
- [ ] **Wallet status updates** in real-time
- [ ] **Metrics update automatically** (every 30 seconds)
- [ ] **Notifications appear** for important events

## 8. Notifications

### 8.1 Telegram Notifications
- [ ] **New whale discovery** sends Telegram message
- [ ] **Bulk import completion** sends Telegram summary
- [ ] **Hunt target added** sends notification
- [ ] **Error alerts** sent for sync failures

### 8.2 In-app Notifications
- [ ] **Success messages** appear after actions
- [ ] **Error messages** show helpful details
- [ ] **Loading indicators** during operations

## 9. Performance

### 9.1 Page Load
- [ ] **Initial load < 3 seconds** on desktop
- [ ] **Tab switching < 1 second**
- [ ] **Filter application < 500ms**

### 9.2 Data Loading
- [ ] **Progressive loading** for large tables
- [ ] **No UI freezing** during data fetch
- [ ] **Error handling** for failed API calls

## 10. Integration Tests

### 10.1 Backend Integration
- [ ] **All API endpoints return** valid JSON
- [ ] **WebSocket endpoint accepts** connections
- [ ] **Celery tasks triggered** from UI actions

### 10.2 Database Operations
- [ ] **Wallet creation** persists to database
- [ ] **Filter queries** return correct results
- [ ] **Transaction data** loads correctly

## Testing Script

Run this quick test script from browser console on the whale insights page:

```javascript
// Quick functionality test
console.log('Testing Whale Tracking UI...');

// Check if all tabs are present
const tabs = document.querySelectorAll('[role="tab"]');
console.log(`Found ${tabs.length} tabs:`, Array.from(tabs).map(t => t.textContent.trim()));

// Check for bulk import button
const bulkImportBtn = document.querySelector('button:contains("Bulk Import")');
console.log('Bulk Import button:', bulkImportBtn ? '✅ Found' : '❌ Missing');

// Check for filters
const filters = document.querySelectorAll('select, input[type="range"]');
console.log(`Found ${filters.length} filter controls`);

// Test WebSocket connection
if (typeof WebSocket !== 'undefined') {
    const ws = new WebSocket(`wss://${window.location.host}/ws/whale-metrics/`);
    ws.onopen = () => console.log('WebSocket: ✅ Connection successful');
    ws.onerror = (e) => console.log('WebSocket: ❌ Connection failed', e);
    setTimeout(() => ws.close(), 1000);
} else {
    console.log('WebSocket: ⚠️ Browser does not support WebSocket');
}
```

## Common Issues & Solutions

### Issue: Tabs not loading
**Check**: JavaScript console for errors
**Fix**: Ensure static files are served correctly

### Issue: Filters not working
**Check**: localStorage permissions in browser
**Fix**: Clear browser cache or check filter JavaScript

### Issue: WebSocket connection failed
**Check**: Daphne server running and Apache proxy configured
**Fix**: Run diagnostic script and check WebSocket setup

### Issue: No real-time updates
**Check**: WebSocket connection status
**Fix**: Verify consumer is correctly processing messages

### Issue: Bulk import slow
**Check**: Celery worker concurrency
**Fix**: Increase Celery workers or optimize task

## Post-Test Actions

After completing all tests:

1. **Document any issues** found
2. **Run diagnostic script** to identify backend problems
3. **Check server logs** for errors during testing
4. **Verify Celery tasks** are processing correctly
5. **Confirm Telegram notifications** are being sent

## Success Criteria

All items marked "✅" in the checklist above indicate the new UI is fully operational. If any items are marked "❌", address those issues before considering the deployment complete.