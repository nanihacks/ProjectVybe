from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class PricedModel(models.Model):
    """Price fields shared by projects, add-ons and services. Amounts are in rupees (INR)."""

    class PricePrefix(models.TextChoices):
        FIXED = "fixed", "Fixed price"
        FROM = "from", "Starting from"

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="In rupees. Leave empty to show no price.",
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Optional genuine discount. Must be lower than the price; the price is shown crossed out.",
    )
    price_prefix = models.CharField(
        max_length=10,
        choices=PricePrefix.choices,
        default=PricePrefix.FIXED,
    )
    price_note = models.CharField(
        max_length=160,
        blank=True,
        help_text="What the price includes, for example 'Source code and setup guide'.",
    )
    show_price = models.BooleanField(
        default=True,
        help_text="Untick to hide the price without deleting it.",
    )

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.sale_price is not None:
            if self.price is None:
                raise ValidationError({"sale_price": "Set a price before setting a sale price."})
            if self.sale_price >= self.price:
                raise ValidationError({"sale_price": "The sale price must be lower than the price."})

    @property
    def has_price(self):
        """True when a price should be shown to visitors."""
        return self.show_price and self.price is not None

    @property
    def on_sale(self):
        return self.has_price and self.sale_price is not None

    @property
    def effective_price(self):
        """What the customer pays: the sale price if there is one, else the price."""
        if not self.has_price:
            return None
        return self.sale_price if self.sale_price is not None else self.price

    @property
    def is_purchasable(self):
        """A price above zero is needed before anything can be paid for online."""
        price = self.effective_price
        return price is not None and price > 0


def to_paise(amount):
    """Rupees (Decimal) to whole paise, as Razorpay expects."""
    return int((Decimal(amount) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def format_inr(value):
    """Format rupees the Indian way: 124999 -> '₹1,24,999', 499.5 -> '₹499.50'."""
    amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, fraction = divmod(abs(amount), 1)
    digits = str(int(whole))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    paise = int(fraction * 100)
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{digits}" + (f".{paise:02d}" if paise else "")
