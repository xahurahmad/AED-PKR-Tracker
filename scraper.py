"""
AED -> PKR daily rate updater
=============================

What this script does:
1. Pulls a genuine benchmark AED->PKR market rate from a free, public,
   no-API-key exchange rate service (Frankfurter, backed by the European
   Central Bank + open FX data). This always works and needs no maintenance.
2. Tries to pull each exchange house's *publicly displayed* rate by
   requesting their page and looking for the rate in the HTML.
3. Writes everything to rates.json, which the website reads.

IMPORTANT REALITY CHECK, read before editing:
Exchange houses do not publish a stable, scrape-friendly rate feed. Most of
them show the rate via JavaScript that calls their own private backend, not
in the raw HTML. That means:
  - Some providers below will come back as "unavailable" until you (or I)
    inspect that specific provider's site with browser DevTools and find
    the real endpoint or the right HTML element.
  - Sites redesign occasionally, which can silently break a scraper. That's
    normal and expected - not a bug in this script.

HOW TO ADD A REAL PROVIDER (step-by-step, once you're ready):
  1. Open the provider's currency converter page in Chrome.
  2. Open DevTools (F12) -> Network tab -> filter to "Fetch/XHR".
  3. Type an amount into their calculator and watch for a new network
     request to appear - click it, check the "Response" tab.
  4. If you see JSON with a rate number in it: that's the endpoint. Copy its
     URL and tell me - I'll wire up a fetch_<provider>() function for it.
  5. If you see NO new request (rate was baked into the page already):
     view page source, search for the number, and tell me the surrounding
     HTML - I'll write a BeautifulSoup selector for it.

Until a provider is wired up, it will show "Live source needed" on the
site, exactly like it does today, so nothing breaks in the meantime.
"""

import json
import sys
import time
import datetime
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}

TIMEOUT = 15


def fetch_benchmark_rate():
    """
    Free, keyless, no-signup FX API. Gives the interbank/market AED->PKR
    rate (not a retail rate any single exchange house would actually pay
    you, but a solid reference point ("today's market rate is X")).
    """
    try:
        r = requests.get(
            "https://api.frankfurter.dev/v1/latest?base=AED&symbols=PKR",
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return round(data["rates"]["PKR"], 4)
    except Exception as e:
        print(f"[benchmark] failed: {e}", file=sys.stderr)
        return None


def fetch_lulu_exchange():
    """
    PLACEHOLDER. LuLu Exchange's converter loads its rate via a backend
    call, not in the raw page HTML, so a plain requests.get() here won't
    see it. Leaving the structure in place so wiring it up later is a
    one-function change. See the module docstring for how to find the
    real endpoint.
    """
    try:
        # Example of the *pattern* once you find the real endpoint:
        # r = requests.get("<endpoint-you-found-in-devtools>", headers=HEADERS, timeout=TIMEOUT)
        # r.raise_for_status()
        # data = r.json()
        # return float(data["rate"])
        return None
    except Exception as e:
        print(f"[lulu] failed: {e}", file=sys.stderr)
        return None


def fetch_al_ansari_exchange():
    """PLACEHOLDER - same situation as LuLu. See module docstring."""
    return None


def fetch_western_union():
    """PLACEHOLDER - same situation. See module docstring."""
    return None


# Providers that currently have NO working fetch function are listed here
# with fetch_fn=None so the site still lists them (as "Live source needed"),
# exactly like your original page.
PROVIDERS = [
    {"name": "Al Ansari Exchange", "fetch_fn": fetch_al_ansari_exchange},
    {"name": "TapTap Send", "fetch_fn": None},
    {"name": "du Pay", "fetch_fn": None},
    {"name": "e& money", "fetch_fn": None},
    {"name": "Botim", "fetch_fn": None},
    {"name": "Index Exchange", "fetch_fn": None},  # manual/published rate below
    {"name": "Redha Al Ansari Exchange", "fetch_fn": None},
    {"name": "LuLu Exchange", "fetch_fn": fetch_lulu_exchange},
    {"name": "Fardan Exchange", "fetch_fn": None},
    {"name": "Western Union", "fetch_fn": fetch_western_union},
    {"name": "Al Rostamani International Exchange", "fetch_fn": None},
]

# Manually-maintained fallback rates for providers without a live source
# yet. Edit this number yourself whenever you check their site, and the
# site will show it with a "Manually updated" status instead of hiding it.
# Leave a provider out of this dict entirely to show "Live source needed".
MANUAL_RATES = {
    "Index Exchange": 75.50,
}


def build_rates():
    result = []
    for p in PROVIDERS:
        name = p["name"]
        rate = None
        status = "Live source needed"

        if p["fetch_fn"] is not None:
            rate = p["fetch_fn"]()
            if rate is not None:
                status = "Live"
            time.sleep(1)  # be polite between requests

        if rate is None and name in MANUAL_RATES:
            rate = MANUAL_RATES[name]
            status = "Manually updated"

        result.append({"name": name, "rate": rate, "status": status})

    return result


def main():
    benchmark = fetch_benchmark_rate()

    output = {
        "updated_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "benchmark_rate": benchmark,
        "benchmark_source": "Frankfurter (ECB/open market data)",
        "providers": build_rates(),
    }

    with open("rates.json", "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
