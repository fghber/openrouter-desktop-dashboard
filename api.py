"""OpenRouter API requests used by the dashboard refresh cycle."""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from config_store import _as_secret, _unique_extra_keys, _usable_secret

def _is_retryable_http_status(code):
    """Transient server errors worth retrying within the existing attempt
    budget; auth/client errors (401/400/403/404) fail fast."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return False
    return code == 429 or 500 <= code <= 599

def _http_retry_delay(resp, default):
    """Seconds to wait before retrying; honors Retry-After on 429 (capped)."""
    try:
        raw = resp.headers.get('Retry-After')
    except Exception:
        return default
    if raw is None:
        return default
    try:
        return min(10.0, max(0.0, float(raw)))
    except (TypeError, ValueError, OverflowError):
        return default

class OpenRouterFetchMixin:
    """Dashboard methods that fetch and aggregate OpenRouter usage."""

    def _fetch_credits(self, headers):
        """Credits API: balance + historical total spend (account level, any key returns same result).
        Returns (balance, global_total_usage); both None = credits fetch failed (distinct from real $0).
        Transient 429/5xx are retried within the attempt budget; 401 and other
        client errors fail fast."""
        balance = None
        global_total_usage = None
        for attempt in range(3):
            try:
                rc = requests.get('https://openrouter.ai/api/v1/credits',
                                  headers=headers, timeout=8)
                if rc.status_code == 200:
                    cd = rc.json().get('data', {})
                    granted = float(cd.get('total_credits', 0) or 0)
                    used    = float(cd.get('total_usage',   0) or 0)
                    balance = granted - used
                    global_total_usage = used
                    break
                if _is_retryable_http_status(rc.status_code) and attempt < 2:
                    time.sleep(_http_retry_delay(rc, 2))
                    continue
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2)
        return balance, global_total_usage

    def _fetch_extra_key_usage(self, key):
        """One extra key's (usage_daily, usage_monthly); (0.0, 0.0) when the key can't be fetched.
        Transient 429/5xx are retried within the attempt budget; 401 and other
        client errors fail fast."""
        for attempt in range(2):
            try:
                rk = requests.get('https://openrouter.ai/api/v1/auth/key',
                                  headers={'Authorization': f'Bearer {key}'},
                                  timeout=8)
                if rk.status_code == 200:
                    kd = rk.json().get('data', {})
                    return (float(kd.get('usage_daily',   0) or 0),
                            float(kd.get('usage_monthly', 0) or 0))
                if _is_retryable_http_status(rk.status_code) and attempt < 1:
                    time.sleep(_http_retry_delay(rk, 1))
                    continue
                break
            except Exception:
                if attempt < 1:
                    time.sleep(1)
        return 0.0, 0.0

    def _fetch_activity(self, mgmt_key):
        """Activity API: UTC-month model TOP 3 + daily breakdown.
        Activity has audit delay (today's spend often appears tomorrow), so it is
        only used for monthly details and TOP3, not for the daily/monthly spend cards.
        Activity periods use UTC regardless of the display timezone."""
        top3 = []
        top3_latest = ''
        daily_breakdown = {}
        now_utc = datetime.now(tz=timezone.utc)
        month_prefix = now_utc.strftime('%Y-%m')
        for attempt in range(3):
            try:
                rg = requests.get(
                    'https://openrouter.ai/api/v1/activity',
                    headers={'Authorization': f'Bearer {mgmt_key}'},
                    timeout=10,
                )
                if rg.status_code == 200:
                    model_cost: dict = {}
                    daily_breakdown: dict = {}
                    latest_date = ''
                    all_data = rg.json().get('data', [])
                    for g in all_data:
                        gdate = g.get('date', '')
                        if not gdate.startswith(month_prefix):
                            continue
                        day = gdate[:10]
                        if day > latest_date:
                            latest_date = day
                        model = g.get('model', '')
                        cost  = float(g.get('usage', 0) or 0)
                        tok_in_value = g.get('prompt_tokens')
                        if tok_in_value is None:
                            tok_in_value = g.get('tokens_prompt', 0)
                        tok_out_value = g.get('completion_tokens')
                        if tok_out_value is None:
                            tok_out_value = g.get('tokens_completion', 0)
                        tok_in  = int(tok_in_value or 0)
                        tok_out = int(tok_out_value or 0)
                        if model:
                            model_cost[model] = model_cost.get(model, 0) + cost
                        if day not in daily_breakdown:
                            daily_breakdown[day] = {'cost': 0.0, 'tokens': 0}
                        daily_breakdown[day]['cost']   += cost
                        daily_breakdown[day]['tokens'] += tok_in + tok_out
                    top3 = sorted(model_cost.items(), key=lambda x: x[1], reverse=True)[:3]
                    top3_latest = latest_date
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2)
        return top3, top3_latest, daily_breakdown

    def _fetch(self):
        key = _as_secret(self.cfg.get('api_key'))
        if not _usable_secret(key):
            return {'error': 'no_key'}
        headers = {'Authorization': f'Bearer {key}'}
        last_err = None
        for attempt in range(3):
            try:
                r = requests.get('https://openrouter.ai/api/v1/auth/key',
                                 headers=headers, timeout=10)
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(2)
        if last_err:
            return {'error': str(last_err)}

        if r.status_code == 401:
            return {'error': '401'}
        if r.status_code != 200:
            return {'error': f'HTTP {r.status_code}'}

        try:
            payload = r.json()
            d = payload.get('data', {}) if isinstance(payload, dict) else {}
            if not isinstance(d, dict):
                d = {}
        except ValueError:
            return {'error': 'invalid_response'}

        # 1. Daily/monthly spend: seed from first auth/key, then sum extra keys only
        # usage_daily reset by OpenRouter officially at UTC 0:00 real-time, no delay, most accurate
        all_daily   = float(d.get('usage_daily',   0) or 0)
        all_monthly = float(d.get('usage_monthly', 0) or 0)
        extra_keys = _unique_extra_keys(self.cfg.get('extra_keys'), key)

        # 2. Credits, extra keys, and activity are independent: fetch them (and each
        #    extra key) concurrently so one slow or retrying endpoint no longer makes
        #    the whole refresh cycle wait on the sum of all timeouts/retries.
        mgmt_key = _as_secret(self.cfg.get('mgmt_key'))
        if not _usable_secret(mgmt_key):
            mgmt_key = ''
        with ThreadPoolExecutor(max_workers=min(8, 2 + len(extra_keys))) as pool:
            credits_fut  = pool.submit(self._fetch_credits, headers)
            activity_fut = pool.submit(self._fetch_activity, mgmt_key) if mgmt_key else None
            extra_futs   = [pool.submit(self._fetch_extra_key_usage, k) for k in extra_keys]

            balance, global_total_usage = credits_fut.result()
            if activity_fut is not None:
                top3, top3_latest, daily_breakdown = activity_fut.result()
            else:
                top3, top3_latest, daily_breakdown = [], '', {}
            for fut in extra_futs:
                daily, monthly = fut.result()
                all_daily   += daily
                all_monthly += monthly

        return {
            'ok':                     True,
            'limit':                  d.get('limit'),
            'limit_rem':              d.get('limit_remaining'),
            'balance':                balance,
            'label':                  d.get('label', ''),
            'top3':                   top3,
            'top3_latest_date':       top3_latest,
            'daily_breakdown':        daily_breakdown,
            'all_daily':              all_daily,             # Sum of usage_daily for all keys, real-time daily spend
            'all_monthly':            all_monthly,           # Sum of usage_monthly for all keys
            'global_total_usage':     global_total_usage,    # Account historical total spend from credits API (None if credits failed)
        }
