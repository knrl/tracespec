from shop.catalog import price_of


def test_price_of_a_known_sku():
    assert price_of("apple") == 120
