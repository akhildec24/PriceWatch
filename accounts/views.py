from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, Min
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, TemplateView

from trackers.models import (
    PriceAlert,
    PriceObservation,
    Product,
    ProductVariant,
    UserTrackingRule,
)
from trackers.services import PriceIntelligence
from .forms import LoginForm, RegisterForm


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = authenticate(
            self.request,
            username=form.cleaned_data['email'],
            password=form.cleaned_data['password1'],
        )
        if user:
            login(self.request, user)
        return response


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def settings_view(request):
    return render(request, 'accounts/settings.html')


@login_required
def dashboard(request):
    """Decision-focused dashboard for the logged-in user."""
    rules = UserTrackingRule.objects.filter(
        user=request.user,
        is_active=True,
    ).select_related('product_variant__product__retailer')

    worth_buying = []
    recently_reduced = []
    continue_waiting = []
    back_in_stock = []
    biggest_savings = []

    now = timezone.now()
    yesterday = now - timedelta(hours=24)

    for rule in rules:
        variant = rule.product_variant
        product = variant.product
        stats = PriceIntelligence.get_stats(variant)
        price_class = PriceIntelligence.classify_price(stats)

        card = {
            'rule': rule,
            'product': product,
            'variant': variant,
            'stats': stats,
            'price_class': price_class,
        }

        # Worth buying now: close to or below recorded minimum
        if stats['lowest_price'] and stats['current_price']:
            if stats['current_price'] <= stats['lowest_price'] * Decimal('1.05'):
                worth_buying.append(card)

        # Recently reduced: price dropped in past 24 hours
        recent_obs = variant.observations.filter(recorded_at__gte=yesterday).order_by('-recorded_at')
        if recent_obs.count() >= 2:
            latest = recent_obs[0]
            prev = recent_obs[1]
            if latest.price and prev.price and latest.price < prev.price:
                recently_reduced.append(card)

        # Continue waiting: above typical price
        if price_class in ('Above average', 'Expensive compared with its recorded history'):
            continue_waiting.append(card)

        # Back in stock: variant became available recently
        recent_avail = variant.observations.filter(recorded_at__gte=yesterday).order_by('-recorded_at')
        if recent_avail.count() >= 2:
            if (recent_avail[0].availability == 'in_stock'
                    and recent_avail[1].availability != 'in_stock'):
                back_in_stock.append(card)

        # Biggest savings: ranked by total reduction
        if stats['total_reduction'] and stats['total_reduction'] > 0:
            biggest_savings.append(card)

    biggest_savings.sort(
        key=lambda c: c['stats']['total_reduction'] or Decimal('0'),
        reverse=True,
    )

    # Unread alerts count
    unread_alerts = PriceAlert.objects.filter(
        tracking_rule__user=request.user,
        is_read=False,
    ).count()

    return render(request, 'accounts/dashboard.html', {
        'worth_buying': worth_buying[:5],
        'recently_reduced': recently_reduced[:5],
        'continue_waiting': continue_waiting[:5],
        'back_in_stock': back_in_stock[:5],
        'biggest_savings': biggest_savings[:5],
        'unread_alerts': unread_alerts,
        'total_tracked': rules.count(),
    })
