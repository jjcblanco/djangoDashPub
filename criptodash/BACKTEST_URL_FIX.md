# Quick Fix - Backtest URL

## ✅ Correct URL

```
http://localhost:8000/backtest/
```

**NOT** `http://localhost:8000/dashboard/backtest/`

## Why?

In `criptodash/urls.py`, the dashboard URLs are included at the root:
```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('dashboard.urls')),  # ← Dashboard at root!
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
]
```

So the `backtest/` path from `dashboard/urls.py` becomes just `/backtest/`.

## All Available URLs

Based on your configuration:

- **Home**: `http://localhost:8000/`
- **Login**: `http://localhost:8000/login/`
- **Register**: `http://localhost:8000/register/`
- **Profile**: `http://localhost:8000/profile/`
- **Technical Analysis**: `http://localhost:8000/technical-analysis/`
- **Run Bot**: `http://localhost:8000/run-bot/`
- **Import Data**: `http://localhost:8000/import-data/`
- **Dashboard Nuevo**: `http://localhost:8000/nuevo/`
- **Backtest**: `http://localhost:8000/backtest/` ✨
- **API Run Bot**: `http://localhost:8000/api/run-bot/`

## Quick Test

1. Make sure your server is running:
   ```bash
   python manage.py runserver
   ```

2. Navigate to:
   ```
   http://localhost:8000/backtest/
   ```

3. You should see the backtest configuration page!

## Fixed Issues

✅ Added missing imports (`BacktestResult`, `OHLCVData`) to `views.py`
✅ Verified URL routing is correct
✅ Confirmed all templates are in place

## If You Still Get 404

1. **Check if server is running**:
   ```bash
   python manage.py runserver
   ```

2. **Verify you're logged in** (the view requires `@login_required`):
   - Go to `http://localhost:8000/login/` first
   - Then navigate to `http://localhost:8000/backtest/`

3. **Check for errors in console**:
   - Look at the terminal where `runserver` is running
   - Check for any import errors or exceptions

4. **Restart the server**:
   ```bash
   # Press Ctrl+C to stop
   python manage.py runserver
   ```

## Navigation Links

You can add this to your dashboard navigation:

```html
<a href="{% url 'backtest' %}">Backtesting</a>
```

Or use the full URL:
```html
<a href="/backtest/">Backtesting</a>
```
