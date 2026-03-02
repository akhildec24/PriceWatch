from importlib import import_module

from .base import RetailerAdapter
from .amazon import AmazonAdapter
from .shopify import ShopifyAdapter
from .woocommerce import WooCommerceAdapter

ADAPTER_REGISTRY = {
    'trackers.adapters.amazon.AmazonAdapter': AmazonAdapter,
    'trackers.adapters.shopify.ShopifyAdapter': ShopifyAdapter,
    'trackers.adapters.woocommerce.WooCommerceAdapter': WooCommerceAdapter,
}


def get_adapter(retailer) -> RetailerAdapter:
    """Return an adapter instance for the given retailer."""
    adapter_class_path = retailer.adapter_class
    if adapter_class_path in ADAPTER_REGISTRY:
        adapter_class = ADAPTER_REGISTRY[adapter_class_path]
    else:
        module_path, class_name = adapter_class_path.rsplit('.', 1)
        module = import_module(module_path)
        adapter_class = getattr(module, class_name)
    return adapter_class(retailer)


def find_retailer_for_url(url, retailers):
    """Find which retailer matches the given URL.

    First pass: match by domain string (fast, no network calls).
    Second pass: try adapter URL validation for generic retailers
    (Shopify/WooCommerce can be on any domain).
    """
    from .base import RetailerAdapter

    domain = RetailerAdapter.get_domain(url)

    # First pass: domain-based matching for known retailers
    for retailer in retailers:
        if retailer.domain and retailer.domain in domain:
            return retailer

    # Second pass: adapter-based validation for generic retailers
    for retailer in retailers:
        if not retailer.domain:
            continue
        # Skip if domain already matched in first pass
        if retailer.domain in domain:
            continue
        adapter = get_adapter(retailer)
        try:
            if adapter.validate_url(url):
                return retailer
        except Exception:
            continue

    return None
