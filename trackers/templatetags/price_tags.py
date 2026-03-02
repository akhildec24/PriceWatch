import json
from decimal import Decimal

from django import template
from django.core.serializers.json import DjangoJSONEncoder

register = template.Library()


class SafeJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


@register.filter
def to_json(value):
    return json.dumps(value, cls=SafeJSONEncoder)
