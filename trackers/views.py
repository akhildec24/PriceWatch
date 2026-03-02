from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.views.decorators.http import require_http_methods

from accounts.models import User
from .adapters.registry import get_adapter, find_retailer_for_url
from .forms import AddProductForm, AlertRuleForm
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


class AddProductView(View):
    """Display the add product form."""

    def get(self, request):
        form = AddProductForm()
        retailers = Retailer.objects.filter(is_active=True)
        return render(request, 'trackers/add_product.html', {
            'form': form,
            'retailers': retailers,
        })


class ProductPreviewView(View):
    """Fetch product data and return a preview via HTMX."""

    def post(self, request):
        form = AddProductForm(request.POST)
        if not form.is_valid():
            return render(request, 'trackers/partials/preview_error.html', {
                'errors': form.errors,
            })

        url = form.cleaned_data['url']
        retailers = Retailer.objects.filter(is_active=True)

        retailer = find_retailer_for_url(url, retailers)
        if not retailer:
            return render(request, 'trackers/partials/preview_error.html', {
                'errors': {'url': ['This retailer is not currently supported.']},
            })

        adapter = get_adapter(retailer)
        try:
            product_data = adapter.fetch_product(url)
        except Exception as e:
            return render(request, 'trackers/partials/preview_error.html', {
                'errors': {'url': [f'Could not fetch product data: {str(e)}']},
            })

        if not product_data.title:
            return render(request, 'trackers/partials/preview_error.html', {
                'errors': {'url': ['Could not extract product information from this page.']},
            })

        # Store product data in session for the confirmation step
        request.session['pending_product'] = {
            'retailer_id': retailer.id,
            'retailer_product_id': product_data.retailer_product_id,
            'canonical_url': product_data.canonical_url,
            'title': product_data.title,
            'brand': product_data.brand,
            'category': product_data.category,
            'image_url': product_data.image_url,
            'currency': product_data.currency,
            'current_price': str(product_data.current_price) if product_data.current_price else '',
            'original_price': str(product_data.original_price) if product_data.original_price else '',
            'availability': product_data.availability,
            'variants': [
                {
                    'variant_identifier': v.variant_identifier,
                    'size': v.size,
                    'colour': v.colour,
                    'storage': v.storage,
                    'configuration': v.configuration,
                    'current_price': str(v.current_price) if v.current_price else '',
                    'original_price': str(v.original_price) if v.original_price else '',
                    'availability': v.availability,
                }
                for v in product_data.variants
            ],
        }

        return render(request, 'trackers/partials/product_preview.html', {
            'product_data': product_data,
            'retailer': retailer,
        })


@method_decorator(login_required, name='dispatch')
class ConfirmTrackingView(View):
    """Confirm tracking and create the product, variant, and tracking rule."""

    def post(self, request):
        pending = request.session.get('pending_product')
        if not pending:
            return redirect('add_product')

        variant_identifier = request.POST.get('variant_identifier', '')
        alert_type = request.POST.get('alert_type', 'any_drop')
        target_price = request.POST.get('target_price', '')
        percentage_drop = request.POST.get('percentage_drop', '')

        with transaction.atomic():
            retailer = Retailer.objects.get(id=pending['retailer_id'])

            product, created = Product.objects.get_or_create(
                retailer=retailer,
                retailer_product_id=pending['retailer_product_id'],
                defaults={
                    'canonical_url': pending['canonical_url'],
                    'title': pending['title'],
                    'brand': pending['brand'],
                    'category': pending['category'],
                    'image_url': pending['image_url'],
                    'currency': pending['currency'],
                    'current_price': Decimal(pending['current_price']) if pending['current_price'] else None,
                    'original_price': Decimal(pending['original_price']) if pending['original_price'] else None,
                    'availability': pending['availability'],
                },
            )

            # Find or create variant
            variants_data = pending.get('variants', [])
            if variants_data:
                variant_data = next(
                    (v for v in variants_data if v['variant_identifier'] == variant_identifier),
                    variants_data[0],
                )
            else:
                variant_data = {
                    'variant_identifier': 'default',
                    'size': '',
                    'colour': '',
                    'storage': '',
                    'configuration': '',
                    'current_price': pending['current_price'],
                    'original_price': pending['original_price'],
                    'availability': pending['availability'],
                }

            variant, v_created = ProductVariant.objects.get_or_create(
                product=product,
                variant_identifier=variant_data['variant_identifier'],
                defaults={
                    'size': variant_data['size'],
                    'colour': variant_data['colour'],
                    'storage': variant_data['storage'],
                    'configuration': variant_data['configuration'],
                    'current_price': Decimal(variant_data['current_price']) if variant_data['current_price'] else None,
                    'availability': variant_data['availability'],
                },
            )

            # Create initial price observation
            if v_created and variant.current_price:
                PriceObservation.objects.create(
                    product_variant=variant,
                    price=variant.current_price,
                    original_price=variant.original_price if hasattr(variant, 'original_price') else None,
                    availability=variant.availability,
                )

            # Create tracking rule
            rule = UserTrackingRule.objects.create(
                user=request.user,
                product_variant=variant,
                starting_price=variant.current_price,
                target_price=Decimal(target_price) if target_price else None,
                percentage_drop=Decimal(percentage_drop) if percentage_drop else None,
                notify_on_any_drop=(alert_type == 'any_drop'),
                notify_on_stock_return=(alert_type == 'stock_return'),
            )

            # Check product limit
            if request.user.tracking_rules.filter(is_active=True).count() > request.user.product_limit:
                messages.warning(request, f'You have reached your product tracking limit ({request.user.product_limit}).')

        del request.session['pending_product']
        messages.success(request, f'Now tracking: {product.title}')
        return redirect('product_detail', pk=product.id)


class WatchlistView(View):
    """Display the user's tracked products."""

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')

        rules = UserTrackingRule.objects.filter(
            user=request.user,
            is_active=True,
        ).select_related('product_variant__product__retailer')

        cards = []
        for rule in rules:
            variant = rule.product_variant
            product = variant.product
            stats = PriceIntelligence.get_stats(variant)
            price_class = PriceIntelligence.classify_price(stats)

            cards.append({
                'rule': rule,
                'product': product,
                'variant': variant,
                'stats': stats,
                'price_class': price_class,
            })

        return render(request, 'trackers/watchlist.html', {
            'cards': cards,
        })


class ProductDetailView(View):
    """Detailed view of a tracked product with price history."""

    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('login')

        product = get_object_or_404(Product, pk=pk)
        variants = product.variants.all()

        # Get the user's tracking rules for this product's variants
        user_rules = UserTrackingRule.objects.filter(
            user=request.user,
            product_variant__in=variants,
            is_active=True,
        ).select_related('product_variant')

        # Get stats for each variant
        variant_data = []
        for variant in variants:
            stats = PriceIntelligence.get_stats(variant)
            price_class = PriceIntelligence.classify_price(stats)
            observations = variant.observations.exclude(price__isnull=True).order_by('recorded_at')[:200]

            # Chart data
            chart_labels = [obs.recorded_at.strftime('%Y-%m-%d %H:%M') for obs in observations]
            chart_prices = [float(obs.price) for obs in observations if obs.price]

            # Latest prediction
            prediction = variant.predictions.first()

            variant_data.append({
                'variant': variant,
                'stats': stats,
                'price_class': price_class,
                'chart_labels': chart_labels,
                'chart_prices': chart_prices,
                'prediction': prediction,
                'observations': observations[:20],
            })

        return render(request, 'trackers/product_detail.html', {
            'product': product,
            'variant_data': variant_data,
            'user_rules': user_rules,
        })


class DeleteTrackingRuleView(View):
    """Delete a tracking rule."""

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('login')

        rule = get_object_or_404(UserTrackingRule, pk=pk, user=request.user)
        rule.is_active = False
        rule.save()
        messages.success(request, 'Stopped tracking this product.')
        return redirect('watchlist')


class UpdateAlertRuleView(View):
    """Update alert settings for a tracking rule."""

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('login')

        rule = get_object_or_404(UserTrackingRule, pk=pk, user=request.user)
        form = AlertRuleForm(request.POST)

        if form.is_valid():
            rule.target_price = form.cleaned_data.get('target_price')
            rule.percentage_drop = form.cleaned_data.get('percentage_drop')
            rule.notify_on_any_drop = form.cleaned_data.get('notify_on_any_drop', False)
            rule.notify_on_stock_return = form.cleaned_data.get('notify_on_stock_return', False)
            rule.save()
            messages.success(request, 'Alert settings updated.')

        return redirect('product_detail', pk=rule.product_variant.product.id)
