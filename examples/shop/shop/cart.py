DISCOUNT_THRESHOLD = 10000


def total(items):
    subtotal = float(sum(items))
    return subtotal * 0.9 if subtotal > DISCOUNT_THRESHOLD else subtotal
