# PriceWatch — Personal Shopping Watchlist

A Django application that tracks product prices from supported retailers, builds price history, and alerts users when prices drop. Positioned as a personal shopping assistant rather than a generic price comparison site.

---

## Product Concept

A user pastes a product URL from a supported shop (Amazon, ASOS, or other retailers). The application:

1. Identifies the retailer
2. Extracts the exact product and variant
3. Records the current price
4. Checks the product at scheduled intervals
5. Builds a price history
6. Alerts the user when the price drops
7. Estimates whether the price is likely to fall further
8. Shows whether the current price is unusually high or low

---

## User Experience

### Adding a Product

The user pastes a URL. Django creates a preview containing:

- Product name
- Retailer
- Product image
- Current price
- Previous price (when available)
- Selected size, colour or configuration
- Stock status
- Seller (where relevant)
- Delivery cost (when available)

The user selects an alert rule:

- Alert me after any price drop
- Alert me when it reaches a target price
- Alert me after a percentage reduction
- Alert me when it returns to its lowest recorded price
- Alert me when my size comes back in stock
- Alert me when the price is likely to rise

### Product Tracking Page

Each tracked product has a dedicated page showing:

- Current price
- Price when tracking started
- Lowest recorded price
- Highest recorded price
- Average price
- Total reduction
- Percentage change
- Last price change
- Number of price changes
- Price history graph
- Stock history
- Prediction and confidence level

Example:

```
Current price: £79.99
Starting price: £109.99
Lowest recorded price: £69.99
Change since tracking began: -27%
Recommendation: Consider waiting
Estimated chance of another reduction within 14 days: 61%
```

The recommendation is clearly described as an estimate, not a guarantee.

---

## Price Intelligence

The app classifies the current price as:

- Excellent price
- Good price
- Typical price
- Above average
- Expensive compared with its recorded history

Plain-English guidance examples:

> This product is currently 18% below its average recorded price. Similar reductions have lasted for approximately four days.

> The price has increased twice during the past seven days. Waiting may not be worthwhile if you need the product soon.

---

## Price Prediction

### Initial Phase

Prediction is introduced gradually. Initially:

> Tracking has started. A prediction will appear after enough price observations have been collected.

### First Prediction System (No ML)

A scoring system based on:

- Current price compared with the average
- Current price compared with the recorded minimum
- Frequency of previous reductions
- Number of days since the last change
- Size of recent price movements
- Whether the product is currently on sale
- Whether the price regularly changes on particular days
- Whether stock is becoming limited

Output:

- Buy score (0–100)
- Recommendation (e.g. "Good time to buy")
- Confidence level (Low / Medium / High)

### Later ML Version

Python models considering:

- Historical prices, day of week, month/season
- Proximity to Black Friday or Christmas
- Retailer sale patterns, product category, product age
- Stock changes, frequency of previous discounts
- Time since previous price change, average discount duration
- Similar products from the same brand

Tools: pandas, NumPy, scikit-learn, XGBoost/LightGBM, Prophet

Present probabilities, not precise future prices:

> There is a moderate chance of a further reduction during the next 14 days.

---

## Retailer Compliance

The application does not assume it can freely scrape every retailer. Each retailer needs its own supported integration and compliance review.

- **Amazon**: Follow current Amazon API and Associates requirements. Do not treat as an ordinary page to scrape.
- **ASOS**: Terms prohibit automated extraction without permission. Requires authorised feed, API, or affiliate arrangement.

Marketing claim: **"Track prices from supported retailers, with new shops added regularly."**

---

## Retailer Integration System

Each retailer has a separate adapter:

```
RetailerAdapter
├── AmazonAdapter
├── ShopDirectAdapter
├── WooCommerceAdapter
├── ShopifyAdapter
└── GenericStructuredDataAdapter
```

Each adapter knows how to:

- Validate the URL
- Find the retailer's product identifier
- Identify the correct variant
- Retrieve the current price
- Retrieve the original price
- Check availability
- Find the product image
- Normalise the product URL
- Detect unavailable or discontinued products

Data source preference order:

1. Official retailer API
2. Authorised affiliate API or product feed
3. Merchant-provided integration
4. Public structured product data (where permitted)
5. Page extraction only when the retailer permits it

### Supporting Independent Shops

Shopify and WooCommerce shops can connect their own stores. Retailers can use the platform to:

- Track competitor prices
- Monitor their products
- Publish price history
- Notify customers about reductions
- Measure how often prices change
- Create wish-list alerts for their customers

---

## Architecture

### Stack

- **Django** + Django templates
- **HTMX** for dynamic interactions
- **Alpine.js** for small interactive behaviour
- **PostgreSQL** for data
- **Redis** for caching and Celery broker
- **Celery** + **Celery Beat** for scheduled tasks
- **Chart.js** for price history graphs

### Background Workers

Celery workers handle:

- Retrieving product information
- Checking prices
- Processing large retailer queues
- Sending alerts
- Updating predictions
- Marking unavailable products
- Retrying failed checks

Celery Beat schedule:

- High-priority products: every hour
- Standard products: every 6 hours
- Inactive products: once per day
- Unavailable products: every 2 days

---

## Data Model

### Retailer
- name, domain, integration_type, is_active, check_frequency, currency, terms_reviewed_at

### Product
- retailer, retailer_product_id, canonical_url, title, brand, category, image_url, currency, current_price, original_price, availability, last_checked_at

### ProductVariant
- product, variant_identifier, size, colour, storage, configuration, current_price, availability

### PriceObservation
- product_variant, price, original_price, delivery_price, availability, seller, recorded_at

Never overwrite price history. Every check creates an observation record.

### UserTrackingRule
- user, product_variant, starting_price, target_price, percentage_drop, notify_on_any_drop, notify_on_stock_return, created_at, is_active

### PricePrediction
- product_variant, prediction_type, predicted_direction, probability, confidence, recommended_action, generated_at, model_version

---

## MVP — Phase One

- User registration
- Paste product URL
- Two or three supported retailers
- Product preview
- Variant selection
- Scheduled price checks
- Price history
- Target-price alerts
- Email notifications
- Personal watchlist
- Basic price graph

No machine learning yet.

## Phase Two

- Price rating
- Buy now or wait recommendation
- Stock alerts
- Browser notifications
- Product collections
- Shared watchlists
- Retailer affiliate links
- Better retry and failure handling
- Duplicate product detection

## Phase Three

- Price forecasting (ML)
- Similar product comparisons
- Cross-retailer product matching
- Seasonal sale analysis
- Mobile-friendly push alerts
- Public deal discovery
- Premium checking intervals
- Retailer and merchant accounts

---

## Dashboard

Focuses on decisions, not generic statistics.

Sections:

- **Worth buying now** — Products close to or below their recorded minimum
- **Recently reduced** — Products that dropped in the past 24 hours
- **Continue waiting** — Products still above their typical price
- **Back in stock** — Products or variants that became available again
- **Biggest savings** — Products ranked by reduction since tracking began

Watchlist card example:

```
Sony WH-1000XM6
Amazon
Now: £319.00
When added: £379.00
Lowest: £309.00
Down £60 since tracking began
Good price
View history
```

---

## Monetisation

### Free
- Track 10 products
- Checks every 12 hours
- Email price alerts
- 90 days of history

### Plus (£3.99–£5.99/month)
- Track 100 products
- More frequent checks
- Stock alerts
- Price predictions
- Unlimited history
- Product collections

### Professional
- Track thousands of products
- Competitor monitoring
- CSV import
- API access
- Team accounts
- Scheduled reports
- Price-change exports

Affiliate commission when users click through and purchase (subject to each retailer's affiliate rules).

---

## Differentiators

- Tracking begins from the exact moment a product is added
- Exact size, colour and configuration tracking
- Honest confidence levels
- Clear explanations behind recommendations
- Stock and price tracking together
- Attractive, uncluttered price-history pages
- Support for independent UK retailers
- No fake urgency or misleading countdowns

---

## Design Philosophy — Dieter Rams

> Good design is as little design as possible.

### Ten Principles

1. Good design is innovative
2. Good design makes a product useful
3. Good design is aesthetic
4. Good design makes a product understandable
5. Good design is unobtrusive
6. Good design is honest
7. Good design is long-lasting
8. Good design is thorough down to the last detail
9. Good design is environmentally-friendly
10. Good design is as little design as possible

### Colour Palette

| Role | Colour | Usage |
|------|--------|-------|
| Neutral Base | Off-White `#F5F5F0` | Primary canvas, panels |
| Neutral Base | Light Grey `#E0E0E0` | Secondary surfaces, borders |
| Structural | Charcoal `#333333` | Text, headers, structural depth |
| Structural | Matte Black `#1A1A1A` | Main body, navigation |
| Functional Accent | Signal Red `#D32F2F` | Key interaction points, alerts, delete actions |
| Functional Accent | Bright Yellow `#F9A825` | Secondary indicators, highlights, attention |
| Occasional Accent | Muted Olive `#827717` | Specific product accents |
| Occasional Accent | Muted Blue `#37474F` | Specific product accents |

### Design Application

- Generous whitespace; reduce visual noise
- Typography-first: clear hierarchy, no decorative fonts
- Functional colour only — accents serve a purpose
- No gradients, no shadows beyond subtle structural separation
- Honest data presentation — no fake urgency, no misleading visuals
- Every element earns its place; remove what is unnecessary
