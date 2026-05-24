"""
Custom throttle classes with named scopes.
Each scope maps to a rate in settings.DEFAULT_THROTTLE_RATES.
Assign the right throttle class to each view instead of the global default.
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

"""
Custom throttle classes with named scopes.
Each scope maps to a rate in settings.DEFAULT_THROTTLE_RATES.
Assign the right throttle class to each view instead of the global default.
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class AuthThrottle(UserRateThrottle):
    """For login/logout - strict limit to prevent brute force."""

    scope = "auth"


class UploadThrottle(UserRateThrottle):
    """For post/reel create - limits upload spam."""

    scope = "upload"


class FeedThrottle(UserRateThrottle):
    """For feed read endpoints - higher limit, read-heavy."""

    scope = "feed"


class InteractionThrottle(UserRateThrottle):
    """For like/comment - moderate limit."""

    scope = "interactions"
