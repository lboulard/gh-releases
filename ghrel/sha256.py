from __future__ import annotations

import hashlib
import logging
import random
import sys
import time
from datetime import timedelta, datetime

import requests

from ghrel.cache import Cache


def to_http_date(date):  # type: (datetime) -> str
    return date.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _get_sha256(
    url, timeout=None, session=None, cache=None
):  # type: (str, int, requests.Session | None, Cache|None) -> (int, str | None)
    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": "curl/7.9.0",
    }
    entry = cache.get(url) if cache else None
    if entry and not entry.expired():
        logging.info(f"# cache hit for {url}")
        headers["If-None-Match"] = entry.etag
        if entry.last_modified:
            headers["If-Modified-Since"] = to_http_date(entry.last_modified)
    if session is None:
        session = requests
    from_cache = False
    with session.get(url, stream=True, timeout=timeout, headers=headers) as response:
        logging.info(f"# {response}")
        sha256 = hashlib.new("SHA256")
        checksum, size = None, -1
        if response.status_code == 200:
            size = 0
            for chunk in response.iter_content(chunk_size=2**16):
                size += len(chunk)
                sha256.update(chunk)
            checksum = sha256.hexdigest().lower()
            if cache:
                if cache.insert(url, size, response, checksum):
                    logging.info(f"# cache save {url}")
                else:
                    logging.warning(f"# cache save failed for {url}")
        elif response.status_code == 304:
            _ = response.content
            if entry:
                from_cache = True
                checksum, size = entry.checksum, entry.size
        else:
            _ = response.content
            print(
                "ERROR: %s returned %d (%s)"
                % (url, response.status_code, response.reason),
                file=sys.stderr,
            )
        return from_cache, size, checksum


def get_sha256(
    url, session, cache=None
):  # type: (str, requests.Session, Cache|None) -> (int, str | None)
    delay, slip = 60, 0
    for tentative in (3, 2, 1, 0):
        try:
            return _get_sha256(url, timeout=30, session=session, cache=cache)
        except requests.exceptions.Timeout as e:
            if tentative == 0:
                raise
            # safety belt: min 30s, max 10mn
            delay = max(10 * 60, min(30, delay))
            # introduce jitter of 30 seconds
            wait = int(random.uniform(delay - 15, delay + 15)) + slip
            slip = delay - wait
            delay *= 2
            print(" ** %s" % str(e))
            print(
                " ** %d tentative%s left, retrying in %s..."
                % (tentative, "s" if tentative > 1 else "", timedelta(seconds=wait))
            )
            time.sleep(wait)
