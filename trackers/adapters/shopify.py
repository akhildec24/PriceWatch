import re
from typing import Optional

import requests

from .base import ProductData, RetailerAdapter, VariantData


class ShopifyAdapter(RetailerAdapter):
    """Shopify adapter — uses the public Shopify product JSON endpoint.

    Shopify stores expose product data at /products.json and
    /products/{handle}.js, which is publicly available structured data
    that merchants opt into by running a Shopify store.
    """

    def validate_url(self, url: str) -> bool:
        domain = self.get_domain(url)
        # Check for Shopify URL patterns: /products/{handle}
        if '/products/' in url:
            return True
        # Check for .myshopify.com domain
        if '.myshopify.com' in domain:
            return True
        return False

    def extract_product_id(self, url: str) -> str:
        # Shopify uses product handles in the URL: /products/{handle}
        match = re.search(r'/products/([a-z0-9\-]+)', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return ''

    def normalise_url(self, url: str) -> str:
        handle = self.extract_product_id(url)
        domain = self.get_domain(url)
        if handle:
            return f'https://{domain}/products/{handle}'
        return url

    def fetch_product(self, url: str) -> ProductData:
        handle = self.extract_product_id(url)
        domain = self.get_domain(url)
        if not handle:
            raise ValueError(f'Could not extract product handle from URL: {url}')

        # Fetch product data from Shopify's public JSON endpoint
        resp = requests.get(
            f'https://{domain}/products/{handle}.json',
            timeout=15,
            headers={'User-Agent': 'PriceWatch/1.0'},
        )
        resp.raise_for_status()
        data = resp.json()
        product = data.get('product', {})

        variants = []
        for v in product.get('variants', []):
            price_str = v.get('price')
            compare_at_str = v.get('compare_at_price')
            price = float(price_str) if price_str else None
            compare_at = float(compare_at_str) if compare_at_str else None

            avail = 'in_stock' if v.get('available', False) else 'out_of_stock'

            variants.append(VariantData(
                variant_identifier=str(v.get('id', '')),
                size=v.get('option1', '') if v.get('option1') and v.get('option1') != 'Default Title' else '',
                colour=v.get('option2', '') if v.get('option2') and v.get('option2') != 'Default Title' else '',
                configuration=v.get('option3', '') if v.get('option3') and v.get('option3') != 'Default Title' else '',
                current_price=price,
                original_price=compare_at,
                availability=avail,
            ))

        # Use first variant for default price
        default_price = variants[0].current_price if variants else None
        default_original = variants[0].original_price if variants else None
        default_avail = variants[0].availability if variants else 'unknown'

        image_url = ''
        if product.get('images'):
            image_url = product['images'][0].get('src', '')

        return ProductData(
            retailer_product_id=handle,
            canonical_url=self.normalise_url(url),
            title=product.get('title', ''),
            brand=product.get('vendor', ''),
            category=product.get('type', ''),
            image_url=image_url,
            currency=self.retailer.currency,
            current_price=default_price,
            original_price=default_original,
            availability=default_avail,
            variants=variants,
        )

    def fetch_variant_price(self, product, variant_identifier: str) -> VariantData:
        domain = product.retailer.domain
        handle = product.retailer_product_id

        resp = requests.get(
            f'https://{domain}/products/{handle}.json',
            timeout=15,
            headers={'User-Agent': 'PriceWatch/1.0'},
        )
        resp.raise_for_status()
        data = resp.json()
        variants = data.get('product', {}).get('variants', [])

        for v in variants:
            if str(v.get('id')) == str(variant_identifier):
                price_str = v.get('price')
                compare_at_str = v.get('compare_at_price')
                return VariantData(
                    variant_identifier=str(v.get('id', '')),
                    current_price=float(price_str) if price_str else None,
                    original_price=float(compare_at_str) if compare_at_str else None,
                    availability='in_stock' if v.get('available') else 'out_of_stock',
                )

        return VariantData(variant_identifier=variant_identifier, availability='unknown')
