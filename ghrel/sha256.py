import hashlib

import requests
import sys


def _get_sha256(url, timeout=None, session=None):
    response = (session if session else requests).get(url, stream=True, timeout=timeout)
    sha256 = hashlib.new("SHA256")
    size = 0
    if response.status_code == 200:
        for chunk in response.iter_content(chunk_size=128):
            size += len(chunk)
            sha256.update(chunk)
    else:
        print(
            "ERROR: %s returned %d (%s)" % (url, response.status_code, response.reason),
            file=sys.stderr,
        )
        sha256 = None
    return (size, sha256.hexdigest().lower() if sha256 else None)


def get_sha256(url, session=None):
    for tentative in range(3, 0, -1):
        try:
            return _get_sha256(url, timeout=5, session=session)
        except requests.exceptions.Timeout as e:
            if tentative == 1:
                raise
            print(" ** %s" % str(e))
            print(
                " ** %d tentative%s left, retrying ..."
                % (tentative - 1, "s" if (tentative - 1) > 1 else "")
            )
