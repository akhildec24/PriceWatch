from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from trackers.models import (
    PriceObservation,
    Product,
    ProductVariant,
    Retailer,
    UserTrackingRule,
)
from trackers.services import PriceIntelligence
from accounts.models import User


class PriceIntelligenceTest(TestCase):
    def setUp(self):
        self.retailer = Retailer.objects.create(
            name='Test Shop',
            domain='testshop.com',
            integration_type=Retailer.INTEGRATION_STRUCTURED_DATA,
            adapter_class='trackers.adapters.shopify.ShopifyAdapter',
        )
        self.product = Product.objects.create(
            retailer=self.retailer,
            retailer_product_id='test-product',
            canonical_url='https://testshop.com/products/test-product',
            title='Test Product',
            current_price=Decimal('79.99'),
            original_price=Decimal('109.99'),
            availability='in_stock',
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_identifier='default',
            current_price=Decimal('79.99'),
            availability='in_stock',
        )

    def test_stats_with_no_observations(self):
        stats = PriceIntelligence.get_stats(self.variant)
        self.assertEqual(stats['observation_count'], 0)
        self.assertIsNone(stats['lowest_price'])

    def test_stats_with_observations(self):
        now = timezone.now()
        PriceObservation.objects.create(
            product_variant=self.variant,
            price=Decimal('109.99'),
            availability='in_stock',
            recorded_at=now - timedelta(days=10),
        )
        PriceObservation.objects.create(
            product_variant=self.variant,
            price=Decimal('89.99'),
            availability='in_stock',
            recorded_at=now - timedelta(days=5),
        )
        PriceObservation.objects.create(
            product_variant=self.variant,
            price=Decimal('79.99'),
            availability='in_stock',
            recorded_at=now,
        )

        stats = PriceIntelligence.get_stats(self.variant)
        self.assertEqual(stats['observation_count'], 3)
        self.assertEqual(stats['lowest_price'], Decimal('79.99'))
        self.assertEqual(stats['highest_price'], Decimal('109.99'))
        self.assertEqual(stats['starting_price'], Decimal('109.99'))
        self.assertEqual(stats['current_price'], Decimal('79.99'))

    def test_classify_price_excellent(self):
        now = timezone.now()
        for i, price in enumerate([100, 95, 90, 85, 70]):
            PriceObservation.objects.create(
                product_variant=self.variant,
                price=Decimal(str(price)),
                availability='in_stock',
                recorded_at=now - timedelta(days=10 - i * 2),
            )

        stats = PriceIntelligence.get_stats(self.variant)
        classification = PriceIntelligence.classify_price(stats)
        self.assertIn('Excellent', classification)

    def test_prediction_requires_min_observations(self):
        prediction = PriceIntelligence.generate_prediction(self.variant)
        self.assertIsNone(prediction)

    def test_prediction_generated_with_enough_data(self):
        now = timezone.now()
        for i, price in enumerate([100, 95, 90, 85, 80, 75]):
            PriceObservation.objects.create(
                product_variant=self.variant,
                price=Decimal(str(price)),
                availability='in_stock',
                recorded_at=now - timedelta(days=10 - i),
            )

        prediction = PriceIntelligence.generate_prediction(self.variant)
        self.assertIsNotNone(prediction)
        self.assertGreaterEqual(prediction.buy_score, 0)
        self.assertLessEqual(prediction.buy_score, 100)
        self.assertIn(prediction.confidence, ['low', 'medium', 'high'])


class RetailerAdapterTest(TestCase):
    def setUp(self):
        self.amazon_retailer = Retailer.objects.create(
            name='Amazon UK',
            domain='amazon.co.uk',
            integration_type=Retailer.INTEGRATION_API,
            adapter_class='trackers.adapters.amazon.AmazonAdapter',
        )
        self.shopify_retailer = Retailer.objects.create(
            name='Shopify Stores',
            domain='shopify.com',
            integration_type=Retailer.INTEGRATION_STRUCTURED_DATA,
            adapter_class='trackers.adapters.shopify.ShopifyAdapter',
        )

    def test_amazon_url_validation(self):
        from trackers.adapters.amazon import AmazonAdapter
        adapter = AmazonAdapter(self.amazon_retailer)
        self.assertTrue(adapter.validate_url('https://www.amazon.co.uk/dp/B0TEST1234'))
        self.assertFalse(adapter.validate_url('https://www.example.com/product/123'))

    def test_amazon_asin_extraction(self):
        from trackers.adapters.amazon import AmazonAdapter
        adapter = AmazonAdapter(self.amazon_retailer)
        asin = adapter.extract_product_id('https://www.amazon.co.uk/dp/B0TEST1234/ref=xxx')
        self.assertEqual(asin, 'B0TEST1234')

    def test_shopify_url_validation(self):
        from trackers.adapters.shopify import ShopifyAdapter
        adapter = ShopifyAdapter(self.shopify_retailer)
        self.assertTrue(adapter.validate_url('https://mystore.com/products/blue-t-shirt'))
        self.assertTrue(adapter.validate_url('https://mystore.myshopify.com/products/test'))
        self.assertFalse(adapter.validate_url('https://mystore.com/collections/all'))

    def test_shopify_handle_extraction(self):
        from trackers.adapters.shopify import ShopifyAdapter
        adapter = ShopifyAdapter(self.shopify_retailer)
        handle = adapter.extract_product_id('https://mystore.com/products/blue-t-shirt')
        self.assertEqual(handle, 'blue-t-shirt')

    def test_find_retailer_for_url(self):
        from trackers.adapters.registry import find_retailer_for_url
        retailers = [self.amazon_retailer, self.shopify_retailer]

        amazon_url = 'https://www.amazon.co.uk/dp/B0TEST1234'
        found = find_retailer_for_url(amazon_url, retailers)
        self.assertEqual(found, self.amazon_retailer)

        shopify_url = 'https://mystore.com/products/blue-t-shirt'
        found = find_retailer_for_url(shopify_url, retailers)
        self.assertEqual(found, self.shopify_retailer)
