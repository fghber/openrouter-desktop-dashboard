"""
Tests for fetch_exchange_rate.

Covers:
- USD returns 1.0 immediately (no API call)
- Successful response from primary API
- Fallback to secondary API when primary fails
- Returns None on all failures
- Handles non-200 status codes
- Handles missing currency in response
"""
import json
from unittest.mock import patch, MagicMock

import pytest

import main


class TestFetchExchangeRate:
    """Tests for fetch_exchange_rate."""

    def test_usd_returns_1_0_without_api_call(self, mock_requests):
        """USD should return 1.0 without making any API call."""
        result = main.fetch_exchange_rate("USD")
        assert result == 1.0
        mock_requests.assert_not_called()

    def test_successful_primary_api(self, mock_requests):
        """Should return rate from primary API on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {"EUR": 0.92, "GBP": 0.79}
        }
        mock_requests.return_value = mock_response

        result = main.fetch_exchange_rate("EUR")
        assert result == 0.92

    def test_fallback_to_secondary_api(self, mock_requests):
        """Should fall back to secondary API when primary returns non-200."""
        # First call (primary) returns 500
        primary_response = MagicMock()
        primary_response.status_code = 500

        # Second call (secondary) returns 200
        secondary_response = MagicMock()
        secondary_response.status_code = 200
        secondary_response.json.return_value = {
            "rates": {"EUR": 0.91}
        }

        mock_requests.side_effect = [primary_response, secondary_response]

        result = main.fetch_exchange_rate("EUR")
        assert result == 0.91

    def test_fallback_when_primary_raises_exception(self, mock_requests):
        """Should fall back to secondary API when primary raises an exception."""
        secondary_response = MagicMock()
        secondary_response.status_code = 200
        secondary_response.json.return_value = {
            "rates": {"JPY": 150.0}
        }

        mock_requests.side_effect = [Exception("Connection error"), secondary_response]

        result = main.fetch_exchange_rate("JPY")
        assert result == 150.0

    def test_returns_none_on_all_failures(self, mock_requests):
        """Should return None when both APIs fail."""
        mock_requests.side_effect = [Exception("Error 1"), Exception("Error 2")]

        result = main.fetch_exchange_rate("GBP")
        assert result is None

    def test_returns_none_when_currency_not_in_rates(self, mock_requests):
        """Should return None when the target currency is not in the response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {"EUR": 0.92, "GBP": 0.79}
        }
        mock_requests.return_value = mock_response

        result = main.fetch_exchange_rate("CAD")
        assert result is None

    def test_returns_none_when_rates_key_missing(self, mock_requests):
        """Should return None when 'rates' key is missing from response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "data"}
        mock_requests.return_value = mock_response

        result = main.fetch_exchange_rate("EUR")
        assert result is None

    def test_handles_float_conversion(self, mock_requests):
        """Should convert rate to float."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rates": {"CNY": "7.2345"}
        }
        mock_requests.return_value = mock_response

        result = main.fetch_exchange_rate("CNY")
        assert result == 7.2345
        assert isinstance(result, float)

    def test_secondary_api_url_contains_currency(self, mock_requests):
        """Secondary API URL should include the target currency."""
        primary_response = MagicMock()
        primary_response.status_code = 500

        secondary_response = MagicMock()
        secondary_response.status_code = 200
        secondary_response.json.return_value = {
            "rates": {"INR": 83.0}
        }

        mock_requests.side_effect = [primary_response, secondary_response]

        main.fetch_exchange_rate("INR")

        # Check the second call URL contains the currency
        second_call_args = mock_requests.call_args_list[1]
        url = second_call_args[0][0] if second_call_args[0] else second_call_args[1].get("url", "")
        assert "INR" in url
