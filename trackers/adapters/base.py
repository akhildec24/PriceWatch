from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


@dataclass
class ProductData:
    """Normalised product data returned by an adapter."""
    retailer_product_id: str = ''
    canonical_url: str = ''
    title: str = ''
    brand: str = ''
    category: str = ''
    image_url: str = ''
    currency: str = 'GBP'
    current_price: Optional[float] = None
    original_price: Optional[float] = None
    availability: str = 'unknown'
    seller: str = ''
    delivery_price: Optional[float] = None
    variants: list = field(default_factory=list)


@dataclass
class VariantData:
    """Normalised variant data."""
    variant_identifier: str = ''
    size: str = ''
    colour: str = ''
    storage: str = ''
    configuration: str = ''
    current_price: Optional[float] = None
    original_price: Optional[float] = None
    availability: str = 'unknown'


class RetailerAdapter:
    """Base adapter class for retailer integrations."""

    def __init__(self, retailer):
        self.retailer = retailer

    def validate_url(self, url: str) -> bool:
        """Check if the URL belongs to this retailer."""
        raise NotImplementedError

    def extract_product_id(self, url: str) -> str:
        """Extract the retailer's product identifier from the URL."""
        raise NotImplementedError

    def normalise_url(self, url: str) -> str:
        """Return a canonical URL for the product."""
        raise NotImplementedError

    def fetch_product(self, url: str) -> ProductData:
        """Fetch product data from the retailer's data source."""
        raise NotImplementedError

    def fetch_variant_price(self, product, variant_identifier: str) -> VariantData:
        """Fetch updated price/availability for a specific variant."""
        raise NotImplementedError

    @staticmethod
    def get_domain(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower()
