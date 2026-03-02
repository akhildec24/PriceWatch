from django.core.management.base import BaseCommand
from django.utils import timezone

from trackers.models import Retailer


class Command(BaseCommand):
    help = 'Seed the database with initial supported retailers'

    def handle(self, *args, **options):
        retailers = [
            {
                'name': 'Amazon UK',
                'domain': 'amazon.co.uk',
                'integration_type': Retailer.INTEGRATION_API,
                'adapter_class': 'trackers.adapters.amazon.AmazonAdapter',
                'check_frequency_minutes': 360,
                'currency': 'GBP',
            },
            {
                'name': 'Shopify Stores',
                'domain': 'shopify.com',
                'integration_type': Retailer.INTEGRATION_STRUCTURED_DATA,
                'adapter_class': 'trackers.adapters.shopify.ShopifyAdapter',
                'check_frequency_minutes': 360,
                'currency': 'GBP',
            },
            {
                'name': 'WooCommerce Stores',
                'domain': 'woocommerce.com',
                'integration_type': Retailer.INTEGRATION_STRUCTURED_DATA,
                'adapter_class': 'trackers.adapters.woocommerce.WooCommerceAdapter',
                'check_frequency_minutes': 360,
                'currency': 'GBP',
            },
        ]

        for r in retailers:
            obj, created = Retailer.objects.get_or_create(
                name=r['name'],
                defaults={**r, 'terms_reviewed_at': timezone.now()},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created retailer: {r["name"]}'))
            else:
                self.stdout.write(f'Retailer already exists: {r["name"]}')
