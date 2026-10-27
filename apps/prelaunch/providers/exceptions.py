
class OTPDeliveryUncertain(Exception):
    """
    The SMS request may have been accepted by the provider,
    but its delivery status could not be confirmed.
    """
    pass
