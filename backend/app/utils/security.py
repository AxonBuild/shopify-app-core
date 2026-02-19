import hashlib
import hmac
import re
from urllib.parse import unquote


SHOP_DOMAIN_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


def is_valid_shop_domain(shop: str) -> bool:
    return bool(SHOP_DOMAIN_REGEX.fullmatch(shop))


def verify_shopify_hmac(params: dict[str, str], api_secret: str) -> bool:
    incoming_hmac = params.get("hmac")
    if not incoming_hmac:
        return False

    filtered_items = []
    for key in sorted(params.keys()):
        if key in {"hmac", "signature"}:
            continue
        filtered_items.append(f"{key}={unquote(str(params[key]))}")

    message = "&".join(filtered_items)
    computed = hmac.new(
        api_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, incoming_hmac)


def mask_token(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"
