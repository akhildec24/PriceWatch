from datetime import timedelta

from celery import shared_task
from django.core.mail import mail_managers, send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .adapters.registry import get_adapter
from .models import (
    PriceAlert,
    PriceObservation,
    PricePrediction,
    Product,
    ProductVariant,
    Retailer,
    UserTrackingRule,
)
from .services import PriceIntelligence


@shared_task(bind=True, max_retries=3)
def check_product_price(self, product_id):
    """Check the current price of a product and record observations."""
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return f'Product {product_id} not found'

    retailer = product.retailer
    if not retailer.is_active:
        return f'Retailer {retailer.name} is not active'

    adapter = get_adapter(retailer)

    for variant in product.variants.all():
        try:
            variant_data = adapter.fetch_variant_price(product, variant.variant_identifier)

            # Record observation
            observation = PriceObservation.objects.create(
                product_variant=variant,
                price=variant_data.current_price,
                original_price=variant_data.original_price,
                availability=variant_data.availability,
            )

            # Update variant current state
            if variant_data.current_price is not None:
                variant.current_price = variant_data.current_price
            variant.availability = variant_data.availability
            variant.save()

            # Check alerts
            check_alerts.delay(variant.id, observation.id)

        except Exception as e:
            # Log error and retry
            print(f'Error checking variant {variant.id}: {e}')
            raise self.retry(exc=e, countdown=300)

    product.last_checked_at = timezone.now()
    product.save()

    return f'Checked product {product.title}'


@shared_task
def check_alerts(variant_id, observation_id):
    """Check if any alert conditions are met for a variant."""
    variant = ProductVariant.objects.get(id=variant_id)
    observation = PriceObservation.objects.get(id=observation_id)

    rules = UserTrackingRule.objects.filter(
        product_variant=variant,
        is_active=True,
    ).select_related('user', 'product_variant__product')

    for rule in rules:
        alert_triggered = False
        alert_type = ''
        message = ''

        previous_obs = variant.observations.exclude(id=observation.id).order_by('-recorded_at').first()

        if rule.notify_on_any_drop and observation.price and previous_obs and previous_obs.price:
            if observation.price < previous_obs.price:
                alert_triggered = True
                alert_type = PriceAlert.ALERT_PRICE_DROP
                message = (
                    f'Price dropped from {previous_obs.price} to {observation.price} '
                    f'for {variant.product.title}'
                )

        if rule.target_price and observation.price:
            if observation.price <= rule.target_price:
                alert_triggered = True
                alert_type = PriceAlert.ALERT_TARGET_REACHED
                message = (
                    f'Price reached your target of {rule.target_price} '
                    f'(now {observation.price}) for {variant.product.title}'
                )

        if rule.percentage_drop and rule.starting_price and observation.price:
            pct = ((rule.starting_price - observation.price) / rule.starting_price) * 100
            if pct >= rule.percentage_drop:
                alert_triggered = True
                alert_type = PriceAlert.ALERT_PERCENTAGE
                message = (
                    f'Price dropped {pct:.1f}% (target: {rule.percentage_drop}%) '
                    f'for {variant.product.title}'
                )

        if rule.notify_on_stock_return and previous_obs:
            if (previous_obs.availability != 'in_stock'
                    and observation.availability == 'in_stock'):
                alert_triggered = True
                alert_type = PriceAlert.ALERT_STOCK_RETURN
                message = f'Back in stock: {variant.product.title}'

        if alert_triggered:
            alert = PriceAlert.objects.create(
                tracking_rule=rule,
                alert_type=alert_type,
                message=message,
                price_at_alert=observation.price,
            )

            # Send email if enabled
            if rule.user.email_alerts_enabled:
                send_alert_email.delay(alert.id)


@shared_task
def send_alert_email(alert_id):
    """Send an email notification for a price alert."""
    alert = PriceAlert.objects.get(id=alert_id)
    rule = alert.tracking_rule
    user = rule.user

    subject = f'PriceWatch Alert: {alert.get_alert_type_display()}'
    plain_message = alert.message

    send_mail(
        subject,
        plain_message,
        None,  # Uses DEFAULT_FROM_EMAIL
        [user.email],
        fail_silently=False,
    )

    return f'Alert email sent to {user.email}'


@shared_task
def update_predictions():
    """Update price predictions for all tracked variants."""
    variants = ProductVariant.objects.filter(
        tracking_rules__is_active=True
    ).distinct()

    for variant in variants:
        PriceIntelligence.generate_prediction(variant)

    return f'Updated predictions for {variants.count()} variants'


@shared_task
def schedule_product_checks():
    """Determine which products need checking and queue tasks."""
    now = timezone.now()

    # High-priority (Plus/Pro tier users): every hour
    # Standard: every 6 hours
    # Inactive: once per day
    # Unavailable: every 2 days

    products = Product.objects.all()

    queued = 0
    for product in products:
        if not product.last_checked_at:
            check_product_price.delay(product.id)
            queued += 1
            continue

        hours_since = (now - product.last_checked_at).total_seconds() / 3600

        # Determine check frequency based on product's tracking rules
        rules = UserTrackingRule.objects.filter(
            product_variant__product=product,
            is_active=True,
        ).select_related('user')

        min_interval = 12  # Default: 12 hours
        for rule in rules:
            if rule.user.check_interval_hours < min_interval:
                min_interval = rule.user.check_interval_hours

        if product.availability == 'out_of_stock':
            min_interval = max(min_interval, 48)
        elif product.availability == 'discontinued':
            continue

        if hours_since >= min_interval:
            check_product_price.delay(product.id)
            queued += 1

    return f'Queued {queued} product checks'
