import hashlib

import requests


def get_sha256(url):
    response = requests.get(url, stream=True)
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
