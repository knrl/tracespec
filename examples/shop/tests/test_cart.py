from shop.cart import total


def test_AC1_total_is_a_float_before_any_discount():
    result = total([100, 250])
    assert result == 350.0
    assert isinstance(result, float)


def test_AC3_orders_over_the_threshold_get_ten_percent_off():
    assert total([15000]) == 13500.0
