from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    TIER_FREE = 'free'
    TIER_PLUS = 'plus'
    TIER_PRO = 'pro'

    TIER_CHOICES = [
        (TIER_FREE, 'Free'),
        (TIER_PLUS, 'Plus'),
        (TIER_PRO, 'Professional'),
    ]

    email = models.EmailField(unique=True)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default=TIER_FREE)
    email_alerts_enabled = models.BooleanField(default=True)
    browser_alerts_enabled = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    @property
    def product_limit(self):
        limits = {
            self.TIER_FREE: 10,
            self.TIER_PLUS: 100,
            self.TIER_PRO: 10000,
        }
        return limits.get(self.tier, 10)

    @property
    def check_interval_hours(self):
        intervals = {
            self.TIER_FREE: 12,
            self.TIER_PLUS: 6,
            self.TIER_PRO: 1,
        }
        return intervals.get(self.tier, 12)
