from django.contrib import admin

from .models import (
    PriceAlert,
    PriceObservation,
    PricePrediction,
    Product,
    ProductVariant,
    Retailer,
    UserTrackingRule,
)


@admin.register(Retailer)
class RetailerAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'integration_type', 'is_active', 'check_frequency_minutes', 'currency']
    list_filter = ['is_active', 'integration_type']
    search_fields = ['name', 'domain']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'retailer', 'current_price', 'availability', 'last_checked_at']
    list_filter = ['retailer', 'availability']
    search_fields = ['title', 'retailer_product_id', 'brand']
    date_hierarchy = 'last_checked_at'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'size', 'colour', 'current_price', 'availability']
    list_filter = ['availability']
    search_fields = ['product__title', 'variant_identifier']


@admin.register(PriceObservation)
class PriceObservationAdmin(admin.ModelAdmin):
    list_display = ['product_variant', 'price', 'availability', 'recorded_at']
    list_filter = ['availability']
    date_hierarchy = 'recorded_at'


@admin.register(UserTrackingRule)
class UserTrackingRuleAdmin(admin.ModelAdmin):
    list_display = ['user', 'product_variant', 'starting_price', 'target_price', 'is_active', 'created_at']
    list_filter = ['is_active', 'notify_on_any_drop', 'notify_on_stock_return']


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ['tracking_rule', 'alert_type', 'price_at_alert', 'is_read', 'sent_at']
    list_filter = ['alert_type', 'is_read']
    date_hierarchy = 'sent_at'


@admin.register(PricePrediction)
class PricePredictionAdmin(admin.ModelAdmin):
    list_display = ['product_variant', 'buy_score', 'confidence', 'recommended_action', 'generated_at']
    list_filter = ['confidence', 'model_version']
