from django.db import models

from accounts.models import User


class Retailer(models.Model):
    INTEGRATION_API = 'api'
    INTEGRATION_AFFILIATE = 'affiliate'
    INTEGRATION_MERCHANT = 'merchant'
    INTEGRATION_STRUCTURED_DATA = 'structured_data'
    INTEGRATION_PAGE_EXTRACTION = 'page_extraction'

    INTEGRATION_CHOICES = [
        (INTEGRATION_API, 'Official API'),
        (INTEGRATION_AFFILIATE, 'Affiliate API / Feed'),
        (INTEGRATION_MERCHANT, 'Merchant Integration'),
        (INTEGRATION_STRUCTURED_DATA, 'Structured Data'),
        (INTEGRATION_PAGE_EXTRACTION, 'Page Extraction'),
    ]

    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=255, unique=True, blank=True)
    integration_type = models.CharField(max_length=30, choices=INTEGRATION_CHOICES)
    adapter_class = models.CharField(max_length=200, help_text='Python path to adapter class')
    is_active = models.BooleanField(default=True)
    check_frequency_minutes = models.IntegerField(default=360)
    currency = models.CharField(max_length=3, default='GBP')
    terms_reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    AVAILABILITY_IN_STOCK = 'in_stock'
    AVAILABILITY_OUT_OF_STOCK = 'out_of_stock'
    AVAILABILITY_DISCONTINUED = 'discontinued'
    AVAILABILITY_UNKNOWN = 'unknown'

    AVAILABILITY_CHOICES = [
        (AVAILABILITY_IN_STOCK, 'In Stock'),
        (AVAILABILITY_OUT_OF_STOCK, 'Out of Stock'),
        (AVAILABILITY_DISCONTINUED, 'Discontinued'),
        (AVAILABILITY_UNKNOWN, 'Unknown'),
    ]

    retailer = models.ForeignKey(Retailer, on_delete=models.CASCADE, related_name='products')
    retailer_product_id = models.CharField(max_length=255)
    canonical_url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500)
    brand = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=200, blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    currency = models.CharField(max_length=3, default='GBP')
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default=AVAILABILITY_UNKNOWN)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['retailer', 'retailer_product_id']
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    variant_identifier = models.CharField(max_length=255, blank=True)
    size = models.CharField(max_length=100, blank=True)
    colour = models.CharField(max_length=100, blank=True)
    storage = models.CharField(max_length=100, blank=True)
    configuration = models.CharField(max_length=200, blank=True)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(max_length=20, choices=Product.AVAILABILITY_CHOICES, default=Product.AVAILABILITY_UNKNOWN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['product', 'variant_identifier']

    def __str__(self):
        parts = [self.size, self.colour, self.storage, self.configuration]
        label = ' / '.join(p for p in parts if p)
        return label or 'Default variant'


class PriceObservation(models.Model):
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='observations')
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    delivery_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    availability = models.CharField(max_length=20, choices=Product.AVAILABILITY_CHOICES, default=Product.AVAILABILITY_UNKNOWN)
    seller = models.CharField(max_length=200, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f'{self.product_variant} — {self.price} — {self.recorded_at:%Y-%m-%d %H:%M}'


class UserTrackingRule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tracking_rules')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='tracking_rules')
    starting_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    percentage_drop = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notify_on_any_drop = models.BooleanField(default=False)
    notify_on_stock_return = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} — {self.product_variant}'


class PriceAlert(models.Model):
    ALERT_PRICE_DROP = 'price_drop'
    ALERT_TARGET_REACHED = 'target_reached'
    ALERT_PERCENTAGE = 'percentage'
    ALERT_STOCK_RETURN = 'stock_return'
    ALERT_LOWEST_PRICE = 'lowest_price'

    ALERT_CHOICES = [
        (ALERT_PRICE_DROP, 'Price Drop'),
        (ALERT_TARGET_REACHED, 'Target Price Reached'),
        (ALERT_PERCENTAGE, 'Percentage Drop Reached'),
        (ALERT_STOCK_RETURN, 'Back in Stock'),
        (ALERT_LOWEST_PRICE, 'Lowest Price Reached'),
    ]

    tracking_rule = models.ForeignKey(UserTrackingRule, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_CHOICES)
    message = models.TextField()
    price_at_alert = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.get_alert_type_display()} — {self.tracking_rule}'


class PricePrediction(models.Model):
    PREDICTION_BUY = 'buy'
    PREDICTION_WAIT = 'wait'
    PREDICTION_NEUTRAL = 'neutral'

    DIRECTION_DOWN = 'down'
    DIRECTION_UP = 'up'
    DIRECTION_STABLE = 'stable'

    CONFIDENCE_LOW = 'low'
    CONFIDENCE_MEDIUM = 'medium'
    CONFIDENCE_HIGH = 'high'

    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='predictions')
    prediction_type = models.CharField(max_length=20, default='scoring')
    predicted_direction = models.CharField(max_length=10, default=DIRECTION_STABLE)
    probability = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    confidence = models.CharField(max_length=10, default=CONFIDENCE_LOW)
    recommended_action = models.CharField(max_length=200, blank=True)
    buy_score = models.IntegerField(default=0)
    explanation = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    model_version = models.CharField(max_length=50, default='scoring-v1')

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f'{self.product_variant} — score {self.buy_score} — {self.confidence}'
