from decimal import Decimal

import pytest

from scripts.reliability.finops_model import amount


def test_storage_proration_preserves_decimal_precision():
    assert amount("0.0912", Decimal(39) * 8 / 730).quantize(Decimal("0.000001")) == Decimal(
        "0.038979"
    )


@pytest.mark.parametrize("price,quantity", [("-1", 8), ("1", -8)])
def test_negative_cost_or_quantity_cannot_reduce_gross_model(price, quantity):
    with pytest.raises(ValueError):
        amount(price, quantity)
