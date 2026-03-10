import json
import re

import requests
from bs4 import BeautifulSoup

from .base import ProductData, RetailerAdapter, VariantData


class AsosAdapter(RetailerAdapter):
    """ASOS adapter — extracts product data from the ASOS product page.

    ASOS product URLs follow the pattern:
      https://www.asos.com/{brand}/{slug}/prd/{product_id}

    The page contains JSON-LD structured data and meta tags that we
    use to extract title, price, image, and availability.
    """

    DOMAIN_PATTERNS = [
        r'asos\.com',
    ]

    PRODUCT_ID_PATTERN = r'/prd/(\d+)'

    def validate_url(self, url: str) -> bool:
        domain = self.get_domain(url)
        return any(re.search(p, domain) for p in self.DOMAIN_PATTERNS)

    def extract_product_id(self, url: str) -> str:
        match = re.search(self.PRODUCT_ID_PATTERN, url)
        if match:
            return match.group(1)
        return ''

    def normalise_url(self, url: str) -> str:
        product_id = self.extract_product_id(url)
        domain = self.get_domain(url)
        if product_id:
            return f'https://{domain}/prd/{product_id}'
        return url

    def fetch_product(self, url: str) -> ProductData:
        product_id = self.extract_product_id(url)
        if not product_id:
            raise ValueError(f'Could not extract product ID from URL: {url}')

        canonical = self.normalise_url(url)

        try:
            return self._fetch_from_page(canonical, product_id)
        except Exception as e:
            raise ValueError(
                f'Could not fetch product data from ASOS: {e}. '
                f'The page may be blocked or the product may no longer exist.'
            )

    def _fetch_from_page(self, url: str, product_id: str) -> ProductData:
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
        brand = ''

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

                brand_data = data.get('brand', {})
                if isinstance(brand_data, dict):
                    brand = brand_data.get('name', '')
                elif isinstance(brand_data, str):
                    brand = brand_data

                offers = data.get('offers', {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}

                if offers.get('price'):
                    try:
                        price = float(offers.get('price'))
                    except (ValueError, TypeError):
                        pass
                if offers.get('availability'):
                    avail_str = offers.get('availability', '')
                    if 'InStock' in avail_str:
                        availability = 'in_stock'
                    elif 'OutOfStock' in avail_str:
                        availability = 'out_of_stock'

        # Fallback: og:title
        if not title:
            og_title = soup.find('meta', property='og:title')
            if og_title:
                title = og_title.get('content', '')

        # Fallback: title tag
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                title = re.sub(r'\s*[:|]\s*ASOS.*$', '', title, flags=re.IGNORECASE)

        # Fallback: og:image
        if not image_url:
            og_image = soup.find('meta', property='og:image')
            if og_image:
                image_url = og_image.get('content', '')

        # Fallback: price from meta tag or data attributes
        if price is None:
            price_meta = soup.find('meta', property='product:price:amount')
            if price_meta:
                try:
                    price = float(price_meta.get('content', ''))
                except (ValueError, TypeError):
                    pass

        # Fallback: currency from meta
        currency_meta = soup.find('meta', property='product:price:currency')
        currency = self.retailer.currency
        if currency_meta:
            currency = currency_meta.get('content', self.retailer.currency)

        # Fallback: availability from meta
        if availability == 'unknown':
            avail_meta = soup.find('meta', property='product:availability')
            if avail_meta:
                avail_str = avail_meta.get('content', '')
                if 'in stock' in avail_str.lower():
                    availability = 'in_stock'
                elif 'out of stock' in avail_str.lower():
                    availability = 'out_of_stock'

        # Fallback: brand from URL path (first segment after domain)
        if not brand:
            path = re.search(r'asos\.com/([^/]+)/', url)
            if path:
                brand = path.group(1).replace('-', ' ').title()

        if not title:
            raise ValueError('Could not extract product title from ASOS page')

        return ProductData(
            retailer_product_id=product_id,
            canonical_url=url,
            title=title,
            brand=brand,
            image_url=image_url,
            currency=currency,
            current_price=price,
            original_price=original_price,
            availability=availability,
        )

    def fetch_variant_price(self, product, variant_identifier: str) -> VariantData:
        return VariantData(
            variant_identifier=variant_identifier,
            availability='unknown',
        )
