# PriceWatch

A personal shopping watchlist that tracks product prices from supported retailers, builds price history, and alerts you when prices drop.

Built with Django, HTMX, Alpine.js, Celery, and Chart.js. Designed following Dieter Rams' ten principles — honest, unobtrusive, and thorough.

## Features

- Paste a product URL to start tracking
- Supports Amazon, Shopify, and WooCommerce retailers
- Exact variant tracking (size, colour, configuration)
- Scheduled price checks via Celery Beat
- Price history with Chart.js graphs
- Price intelligence: buy score, recommendation, confidence level
- Alert rules: any drop, target price, percentage drop, stock return
- Decision-focused dashboard (worth buying, recently reduced, biggest savings)
- Email notifications

## Quick Start

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Seed supported retailers
python manage.py seed_retailers

# Set up Celery Beat schedule
python manage.py setup_schedule

# Create a superuser (optional, for admin)
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

## Running Celery Workers

In separate terminals:

```bash
# Redis must be running
redis-server

# Celery worker
celery -A pricewatch worker -l info

# Celery beat scheduler
celery -A pricewatch beat -l info
```

## Architecture

```
pricewatch/          # Django project settings, Celery config
accounts/            # Custom user model, auth, dashboard
trackers/            # Models, views, adapters, services, tasks
  adapters/          # Retailer adapter pattern
    base.py          # Abstract RetailerAdapter
    amazon.py        # Amazon adapter (API-based)
    shopify.py       # Shopify adapter (public JSON endpoint)
    woocommerce.py   # WooCommerce adapter (structured data)
    registry.py      # Adapter lookup and URL matching
  services.py        # PriceIntelligence scoring system
  tasks.py           # Celery tasks for price checks, alerts, predictions
templates/           # Django templates with Dieter Rams design
static/css/          # Minimal, functional CSS
```

## Design System

Following Dieter Rams' principles with a neutral, functional palette:

- **Off-White / Light Grey** — primary canvas and panels
- **Charcoal / Matte Black** — structural depth and text
- **Signal Red** — alerts and destructive actions
- **Bright Yellow** — key interaction points and highlights

No gradients, no decorative shadows, no fake urgency.

## Retailer Compliance

Each retailer has its own adapter with a compliance review. The application does not scrape retailers that prohibit automated extraction. See `DESIGN.md` for the full compliance policy.

## Roadmap

- **Phase 1 (MVP)**: User registration, URL tracking, scheduled checks, alerts, watchlist, price graph
- **Phase 2**: Price rating, buy/wait recommendations, stock alerts, collections, affiliate links
- **Phase 3**: ML-based price forecasting, cross-retailer matching, seasonal analysis, merchant accounts

See `DESIGN.md` for the complete product specification.
