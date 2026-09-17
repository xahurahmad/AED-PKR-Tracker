"""
AED -> PKR daily rate updater
=============================

What this script does:
1. Pulls a genuine benchmark AED->PKR market rate from a free, public,
   no-API-key exchange rate service (open.er-api.com, covers 160+
   currencies including AED and PKR).
2. Pulls several exchange houses' AED->PKR transfer rate from Masarif.ae,
   a UAE financial comparison site that publishes each provider's rate
   in plain page text (no login, no JavaScript needed to read it).
3. Writes everything to rates.json, which the website reads.

IMPORTANT HONESTY NOTES:
- Masarif.ae is a third-party comparison site, not each exchange house's
  own official page. It sometimes marks its own data "stale" (updated
  every few days rather than every minute). We show whatever it has,
  labelled "Community-sourced (Masarif.ae)" so it's clear where it's
  from, rather than pretending it's each provider's live official rate.
- A handful of providers on Masarif show obviously wrong placeholder
  numbers (flat 100.00 or 50.00 for every historical entry - clearly
  not a real AED-PKR rate). SANE_RATE_RANGE below filters those out
  automatically so we never show a number we know is fake.
- TapTap Send, du Pay, e& money, Botim, and Western Union are apps/
  global remitters, not traditional UAE exchange houses, so Masarif
  doesn't track them. They stay "Live source needed" until a real
  source is found for each - see HOW TO ADD A REAL PROVIDER below.

HOW TO ADD A REAL PROVIDER (for the ones still unwired):
  1. Open the provider's currency converter page in Chrome.
  2. Open DevTools (F12) -> Network tab -> filter to "Fetch/XHR".
  3. Type an amount into their calculator and watch for a new network
     request to appear - click it, check the "Response" tab.
  4. If you see JSON with a rate number in it: that's the endpoint. Copy
     its URL and tell me - I'll wire up a fetch_<provider>() function.
  5. If you see NO new request (rate was baked into the page already):
     view page source, search for the number, and tell me the
     surrounding HTML - I'll write a selector for it.
"""

import json
import re
import sys
import time
import datetime
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}

TIMEOUT = 15

# Any scraped rate outside this range is treated as bad data and discarded.
# AED->PKR has realistically been roughly 60-100 in recent years; widen
# this later if the real rate ever moves outside it.
SANE_RATE_RANGE = (60.0, 100.0)


def fetch_benchmark_rate():
    """
    Free, keyless FX API covering 160+ currencies (including AED and PKR),
    updated once daily. Attribution: data from exchangerate-api.com.
    """
    try:
        r = requests.get(
            "https://open.er-api.com/v6/latest/AED",
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("result") != "success":
            raise ValueError(f"API returned: {data.get('result')}")
        return round(data["rates"]["PKR"], 4)
    except Exception as e:
        print(f"[benchmark] failed: {e}", file=sys.stderr)
        return None


def fetch_masarif_rate(slug):
    """
    Generic fetcher for any exchange house Masarif.ae tracks. Looks for
    the "1 AED = XX.XX PKR" text that appears on each provider's page,
    and rejects anything outside SANE_RATE_RANGE as bad data.
    """
    url = f"https://masarif.ae/currency-exchanges/{slug}/currency-exchange-rates/pkr"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()

        match = re.search(r"1\s*AED\s*=\s*([\d]+\.?[\d]*)\s*PKR", r.text)
        if not match:
            return None

        rate = float(match.group(1))

        if not (SANE_RATE_RANGE[0] <= rate <= SANE_RATE_RANGE[1]):
            print(f"[masarif:{slug}] rejected implausible rate {rate}", file=sys.stderr)
            return None

        return rate

    except Exception as e:
        print(f"[masarif:{slug}] failed: {e}", file=sys.stderr)
        return None


def fetch_al_ansari_exchange():
    return fetch_masarif_rate("al-ansari-exchange")


def fetch_lulu_exchange():
    return fetch_masarif_rate("lulu-international-exchange")


def fetch_index_exchange():
    return fetch_masarif_rate("index-exchange")


def fetch_al_rostamani_exchange():
    return fetch_masarif_rate("al-rostamani-international-exchange")


# Providers with no working live source yet get fetch_fn=None, so the
# site still lists them (as "Live source needed"), same as before.
PROVIDERS = [
    {"name": "Al Ansari Exchange", "fetch_fn": fetch_al_ansari_exchange},
    {"name": "TapTap Send", "fetch_fn": None},
    {"name": "du Pay", "fetch_fn": None},
    {"name": "e& money", "fetch_fn": None},
    {"name": "Botim", "fetch_fn": None},
    {"name": "Index Exchange", "fetch_fn": fetch_index_exchange},
    {"name": "Redha Al Ansari Exchange", "fetch_fn": None},  # no PKR data on Masarif
    {"name": "LuLu Exchange", "fetch_fn": fetch_lulu_exchange},
    {"name": "Fardan Exchange", "fetch_fn": None},  # Masarif shows fake placeholder data
    {"name": "Western Union", "fetch_fn": None},
    {"name": "Al Rostamani International Exchange", "fetch_fn": fetch_al_rostamani_exchange},
]

# Manually-maintained fallback rates, used only if a provider's live fetch
# fails on a given day (keeps the site from suddenly going blank for it).
# Edit this number yourself whenever you check their site directly.
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
                status = "Community-sourced (Masarif.ae)"
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
        "benchmark_source": "open.er-api.com (exchangerate-api.com)",
        "providers": build_rates(),
    }

    with open("rates.json", "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
