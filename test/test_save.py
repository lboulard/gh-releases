import json
import unittest
from collections import namedtuple
from io import StringIO
from textwrap import dedent

from ghrel.model import Asset, Release, ReleaseJsonEncoder

GithubRelease = namedtuple("GithubRelease", "title, body, tag_name")
GithubReleaseAsset = namedtuple(
    "GithubReleaseAsset", "name, size, browser_download_url, content_type"
)


class TestJsonEncoding(unittest.TestCase):
    def test_encoding(self):
        rel = Release(GithubRelease(title="", body="", tag_name="test_release"))
        asset = GithubReleaseAsset(
            name="test-asset.txt",
            size=42,
            browser_download_url="https://github.com/test-project/releases/test-release/assets/download/test-assets.txt",
            content_type="text/plain",
        )
        rel.add_asset(Asset(from_gh_asset=asset))
        #
        io = StringIO()
        json.dump([rel], io, cls=ReleaseJsonEncoder)
        expected = dedent(
            """\
        [
          {
            "title": "",
            "description": "",
            "tag": "test_release",
            "assets": [
              {
                "name": "test-asset.txt",
                "size": 42,
                "url": "https://github.com/test-project/releases/test-release/assets/download/test-assets.txt",
                "content_type": "text/plain",
                "checksum": ""
              }
            ]
          }
        ]
        """
        ).splitlines()
        output = io.getvalue().splitlines(False)
        self.assertEqual(output, expected)
