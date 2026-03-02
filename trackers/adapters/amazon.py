import json
import re

import requests
from bs4 import BeautifulSoup

from .base import ProductData, RetailerAdapter, VariantData


class AmazonAdapter(RetailerAdapter):
    """Amazon adapter — uses Product Advertising API / Creators API in production.

    For development without API keys, falls back to extracting structured
    data (JSON-LD / meta tags) from the product page.
    """

    DOMAIN_PATTERNS = [
        r'amazon\.co\.uk',
        r'amazon\.com',
        r'amazon\.de',
        r'amazon\.fr',
        r'amazon\.it',
        r'amazon\.es',
        r'amazon\.ca',
    ]

    ASIN_PATTERNS = [
        r'/dp/([A-Z0-9]{10})',
        r'/gp/product/([A-Z0-9]{10})',
        r'/gp/aw/d/([A-Z0-9]{10})',
        r'/product/([A-Z0-9]{10})',
        r'/([A-Z0-9]{10})(?:/|\?|$)',
    ]

    def validate_url(self, url: str) -> bool:
        domain = self.get_domain(url)
        return any(re.search(p, domain) for p in self.DOMAIN_PATTERNS)

    def extract_product_id(self, url: str) -> str:
        for pattern in self.ASIN_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return ''

    def normalise_url(self, url: str) -> str:
        asin = self.extract_product_id(url)
        domain = self.get_domain(url)
        if asin:
            return f'https://{domain}/dp/{asin}'
        return url

    def fetch_product(self, url: str) -> ProductData:
        asin = self.extract_product_id(url)
        if not asin:
            raise ValueError(f'Could not extract ASIN from URL: {url}')

        canonical = self.normalise_url(url)

        try:
            return self._fetch_from_page(canonical, asin)
        except Exception as e:
            raise ValueError(
                f'Could not fetch product data: {e}. '
                f'Amazon API configuration required for reliable data access.'
            )

    def _fetch_from_page(self, url: str, asin: str) -> ProductData:
        resp = requests.get(
            url,
            timeout=15,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'en-GB,en;q=0.9',
            },
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'lxml')

        title = ''
        price = None
        original_price = None
        availability = 'unknown'
        image_url = ''

        # Try JSON-LD structured data
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue

            if isinstance(data, list):
                data = data[0] if data else {}

            if data.get('@type') in ('Product', 'product'):
                title = data.get('name', '')
                image = data.get('image', '')
                if isinstance(image, list):
                    image = image[0] if image else ''
                image_url = image

                offers = data.get('offers', {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}

                if offers.get('price'):
                    price = float(offers.get('price'))
                if offers.get('availability'):
                    avail_str = offers.get('availability', '')
                    if 'InStock' in avail_str:
                        availability = 'in_stock'
                    elif 'OutOfStock' in avail_str:
                        availability = 'out_of_stock'

        # Fallback: title from <title> tag
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                title = re.sub(r'^Amazon\.\w+:\s*', '', title)
                title = re.sub(r'\s*[:\-]\s*Amazon\.\w+.*$', '', title)

        # Fallback: og:title
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content', '')

        # Fallback: og:image
        if not image_url:
            og_image = soup.find('meta', property='og:image')
            if og_image:
                image_url = og_image.get('content', '')

        # Fallback: price from a-price spans
        if price is None:
            price_span = soup.find('span', class_='a-price')
            if price_span:
                price_whole = price_span.find('span', class_='a-price-whole')
                price_fraction = price_span.find('span', class_='a-price-fraction')
                if price_whole and price_fraction:
                    whole = price_whole.get_text(strip=True).replace(',', '').rstrip('.')
                    frac = price_fraction.get_text(strip=True)
                    try:
                        price = float(f'{whole}.{frac}')
                    except ValueError:
                        pass

        # Fallback: original price from a-text-strike
        if original_price is None:
            strike = soup.find('span', class_='a-text-strike')
            if strike:
                price_text = strike.get_text(strip=True).replace('£', '').replace(',', '')
                try:
                    original_price = float(price_text)
                except ValueError:
                    pass

        if not title:
            raise ValueError('Could not extract product title from page')

        return ProductData(
            retailer_product_id=asin,
            canonical_url=url,
            title=title,
            image_url=image_url,
            currency=self.retailer.currency,
            current_price=price,
            original_price=original_price,
            availability=availability,
        )

    def fetch_variant_price(self, product, variant_identifier: str) -> VariantData:
        return VariantData(
            variant_identifier=variant_identifier,
            availability='unknown',
        )
