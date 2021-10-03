import json


# https://pygithub.readthedocs.io/en/latest/github_objects/GitReleaseAsset.html
class Asset:
    def __init__(self, from_gh_asset=None):
        if not from_gh_asset:
            raise Exception("missing asset content")
        asset = from_gh_asset
        self.name = asset.name
        self.size = asset.size
        self.url = asset.browser_download_url
        self.content_type = asset.content_type
        self.checksum = ""


# https://pygithub.readthedocs.io/en/latest/github_objects/GitRelease.html
class Release:
    def __init__(self, from_gh_release=None):
        if not from_gh_release:
            raise Exception("missing release content")
        rel = from_gh_release
        self.title = rel.title
        self.description = rel.body
        self.tag = rel.tag_name
        self.assets = []

    def add_asset(self, asset):
        self.assets.append(asset)


class ReleaseJsonEncoder(json.JSONEncoder):
    def __init__(self, **kwargs):
        args = {**kwargs, **dict(indent=2, sort_keys=False)}
        super().__init__(**args)

    def default(self, o):
        return o.__dict__
