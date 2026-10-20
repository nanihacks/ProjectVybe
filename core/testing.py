from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_static.models import StaticDevice


def force_login_verified(client, user):
    """Log a test client in as `user` with the 2FA check already passed.

    The admin refuses users who have not verified a one-time-password device,
    so plain `client.force_login()` no longer reaches it.
    """
    client.force_login(user)
    device, _ = StaticDevice.objects.get_or_create(
        user=user, name="test-device", defaults={"confirmed": True}
    )
    session = client.session
    session[DEVICE_ID_SESSION_KEY] = device.persistent_id
    session.save()
    return device
