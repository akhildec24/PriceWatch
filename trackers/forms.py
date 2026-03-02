from django import forms


class AddProductForm(forms.Form):
    url = forms.URLField(
        label='Product URL',
        max_length=1000,
        widget=forms.URLInput(attrs={
            'placeholder': 'https://www.example-shop.co.uk/product/...',
            'class': 'input',
        }),
    )


class AlertRuleForm(forms.Form):
    ALERT_CHOICES = [
        ('any_drop', 'Alert me after any price drop'),
        ('target_price', 'Alert me when it reaches a target price'),
        ('percentage', 'Alert me after a percentage reduction'),
        ('lowest_price', 'Alert me when it returns to its lowest recorded price'),
        ('stock_return', 'Alert me when my size comes back in stock'),
    ]

    alert_type = forms.ChoiceField(
        choices=ALERT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'radio-group'}),
        initial='any_drop',
    )
    target_price = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'input',
            'placeholder': 'e.g. 80.00',
            'step': '0.01',
        }),
    )
    percentage_drop = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'input',
            'placeholder': 'e.g. 20',
            'step': '0.01',
        }),
    )
    notify_on_any_drop = forms.BooleanField(required=False)
    notify_on_stock_return = forms.BooleanField(required=False)
