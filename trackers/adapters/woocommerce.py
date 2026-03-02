import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import ProductData, RetailerAdapter, VariantData


class WooCommerceAdapter(RetailerAdapter):
    """WooCommerce adapter — uses structured data (JSON-LD / microdata)
    from WooCommerce product pages.

    WooCommerce stores expose product data via structured data in the
    HTML, which is publicly available. For merchant-connected stores,
    the WooCommerce REST API could be used instead.
    """

    def validate_url(self, url: str) -> bool:
        # Check for WooCommerce URL patterns: /product/{slug}
        if '/product/' in url:
            return True
        return False

    def extract_product_id(self, url: str) -> str:
        # WooCommerce uses product slugs: /product/{slug}
        match = re.search(r'/product/([a-z0-9\-]+)', url, re.IGNORECASE)
        if match:
            return match.group(1)
        return ''

    def normalise_url(self, url: str) -> str:
        slug = self.extract_product_id(url)
        domain = self.get_domain(url)
        if slug:
            return f'https://{domain}/product/{slug}'
        return url

    def fetch_product(self, url: str) -> ProductData:
        resp = requests.get(
            url,
            timeout=15,
            headers={'User-Agent': 'PriceWatch/1.0'},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'lxml')

        # Try JSON-LD structured data first
        product_data = self._parse_json_ld(soup, url)
        if product_data.title:
            return product_data

        # Fallback to microdata / meta tags
        return self._parse_meta_tags(soup, url)

    def _parse_json_ld(self, soup, url: str) -> ProductData:
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            import json
            try:
                data = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(data, list):
                data = data[0] if data else {}

            if data.get('@type') in ('Product', 'product'):
                offers = data.get('offers', {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}

                price = None
                if offers.get('price'):
                    price = float(offers.get('price'))
                elif offers.get('lowPrice'):
                    price = float(offers.get('lowPrice'))

                availability = 'unknown'
                avail_str = offers.get('availability', '')
                if 'InStock' in avail_str:
                    availability = 'in_stock'
                elif 'OutOfStock' in avail_str:
                    availability = 'out_of_stock'
                elif 'Discontinued' in avail_str:
                    availability = 'discontinued'

                image = data.get('image', '')
                if isinstance(image, list):
                    image = image[0] if image else ''

                return ProductData(
                    retailer_product_id=self.extract_product_id(url),
                    canonical_url=self.normalise_url(url),
                    title=data.get('name', ''),
                    brand=data.get('brand', {}).get('name', '') if isinstance(data.get('brand'), dict) else str(data.get('brand', '')),
                    category=data.get('category', ''),
                    image_url=image,
                    currency=offers.get('priceCurrency', self.retailer.currency),
                    current_price=price,
                    availability=availability,
                )
        return ProductData()

    def _parse_meta_tags(self, soup, url: str) -> ProductData:
        title = ''
        title_tag = soup.find('meta', property='og:title')
        if title_tag:
            title = title_tag.get('content', '')
        elif soup.find('title'):
            title = soup.find('title').get_text(strip=True)

        image = ''
        image_tag = soup.find('meta', property='og:image')
        if image_tag:
            image = image_tag.get('content', '')

        price = None
        price_tag = soup.find('meta', property='product:price:amount')
        if price_tag:
            try:
                price = float(price_tag.get('content', ''))
            except ValueError:
                pass

        currency = self.retailer.currency
        curr_tag = soup.find('meta', property='product:price:currency')
        if curr_tag:
            currency = curr_tag.get('content', currency)

        return ProductData(
            retailer_product_id=self.extract_product_id(url),
            canonical_url=self.normalise_url(url),
            title=title,
            image_url=image,
            currency=currency,
            current_price=price,
        )

    def fetch_variant_price(self, product, variant_identifier: str) -> VariantData:
        # Re-fetch the product page for variant data
        data = self.fetch_product(product.canonical_url)
        for v in data.variants:
            if v.variant_identifier == variant_identifier:
                return v
        return VariantData(variant_identifier=variant_identifier, availability='unknown')
