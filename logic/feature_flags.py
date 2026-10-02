"""Server-side rollout gates for the phase 1-6 transactional paths."""

from django.conf import settings


ACCOUNTING_GATEWAY = "accounting_gateway"
PROCUREMENT = "procurement"
FULFILLMENT = "fulfillment_reservations"
ACTUAL_COST_PRODUCTION = "actual_cost_production"
UNIFIED_DELIVERY = "unified_delivery"

SETTING_BY_FLAG = {
    ACCOUNTING_GATEWAY: "FEATURE_ACCOUNTING_GATEWAY",
    PROCUREMENT: "FEATURE_UNIFIED_PROCUREMENT",
    FULFILLMENT: "FEATURE_FULFILLMENT_RESERVATIONS",
    ACTUAL_COST_PRODUCTION: "FEATURE_ACTUAL_COST_PRODUCTION",
    UNIFIED_DELIVERY: "FEATURE_UNIFIED_DELIVERY",
}


class FeatureDisabledError(ValueError):
    pass


def is_enabled(name):
    try:
        setting = SETTING_BY_FLAG[name]
    except KeyError as exc:
        raise ValueError(f"Unknown feature flag: {name}") from exc
    return bool(getattr(settings, setting, True))


def require_feature(name):
    if not is_enabled(name):
        raise FeatureDisabledError(
            f"Feature '{name}' is disabled for staged rollout."
        )


def rollout_status():
    return {name: is_enabled(name) for name in SETTING_BY_FLAG}
