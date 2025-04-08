import requests
from decimal import Decimal
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)  # Use Django logging instead of print statements

def fetch_live_exchange_rate(target_currency):
    """Fetch real-time exchange rate from API with caching and error handling."""
    if target_currency == "ETB":
        return Decimal("1.0")

    cache_key = f"exchange_rate_{target_currency}"
    cached_rate = cache.get(cache_key)

    if cached_rate:
        logger.info(f"Cache hit for {target_currency}: {cached_rate}")
        return Decimal(str(cached_rate))

    api_key = settings.EXCHANGE_RATE_API_KEY
    base_currency = "ETB"
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base_currency}"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            logger.error(f"Error fetching exchange rate: {response.status_code}, {response.text}")
            return Decimal("1.0")

        data = response.json()
        logger.info(f"API Response: {data}")

        if not isinstance(data, dict) or "conversion_rates" not in data:
            logger.warning(f"Invalid API response format: {data}")
            return Decimal("1.0")

        conversion_rates = data["conversion_rates"]
        exchange_rate = conversion_rates.get(target_currency)

        if exchange_rate is None:
            logger.warning(f"Exchange rate for {target_currency} not found. Using fallback.")
            return Decimal("1.0")

        # Cache the exchange rate for 6 hours
        cache.set(cache_key, exchange_rate, timeout=60 * 60 * 6)

        return Decimal(str(exchange_rate))

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching exchange rate: {e}")
        return Decimal("1.0")
