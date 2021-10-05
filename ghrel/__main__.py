#!/usr/bin/env python3

import json
import os
import os.path
import sys

import requests
import tomli
from github import Github

from .model import Asset, Release, ReleaseJsonEncoder
from .sha256 import get_sha256

# https://pygithub.readthedocs.io/en/latest/


def make_checksums(name, releases, session=None):
    for release in releases:
        title = release.title or release.tag
        for asset in release.assets:
            print(f"{name}: SHA256 {title} / {asset.name}")
            size, sha256 = get_sha256(asset.url, session=session)
            if size != asset.size:
                print(
                    f"{name}: SHA256 {title} / {asset.name} size {size} != {asset.size} mismatch"
                )
            elif sha256:
                asset.checksum = "sha256:" + sha256
                print(f"{name}: SHA256 {title} / {asset.name} sha256:{sha256}")


class GithubWorker:
    def __init__(self):
        self.g = Github()
        self.session = requests.Session()

    def _get_assets(self, release, gh_release):
        for gh_asset in gh_release.get_assets():
            asset = Asset(from_gh_asset=gh_asset)
            release.add_asset(asset)
        return release

    def get_releases(self, name, project, count):
        repo = self.g.get_repo(project)
        releases = []
        for gh_release in repo.get_releases():
            if gh_release.draft or gh_release.prerelease:
                continue
            release = Release(from_gh_release=gh_release)
            self._get_assets(release, gh_release)
            releases.append(release)
            if not release.assets:
                print(
                    f"{name}: ** WARNING skipping {release.tag}, no assets found",
                    file=os.stderr,
                )
                continue
            if len(releases) == count:
                break
        make_checksums(name, releases, session=self.session)
        return dict(
            name=name, project=repo.full_name, url=repo.html_url, releases=releases
        )


def save_to(output_path, releases):
    with open(output_path, "w+") as w:
        json.dump(releases, w, cls=ReleaseJsonEncoder)


def run(projects, outdir, count=1):
    failed = False
    mk_outdir = not os.path.exists(outdir)
    stderr = sys.stderr
    gw = GithubWorker()
    for name, args in projects.items():
        output = name + ".json"
        if "output" in args:
            output = args["output"]
        if not output:
            print(f"{name}: ** ERROR missing output filename", file=stderr)
            failed = True
            continue
        if not "project" in args:
            printf(f"{name}: * ERROR missing project name", file=stderr)
            failed = True
            continue
        output_path = os.path.join(outdir, output)
        print(f"{name}: ... getting releases")
        count = args.get("count", count)
        releases = gw.get_releases(name, args["project"], count)
        print(f"{name}: writing {output_path}")
        if mk_outdir:
            os.makedirs(outdir, exist_ok=True)
            mk_outdir = False
        save_to(output_path, releases)
    return failed


def recurs_projects(gh_configs):
    projects, values = {}, {}
    for key, value in gh_configs.items():
        if isinstance(value, dict):
            nested_projects, nested_values = recurs_projects(value)
            if nested_projects:
                nested_dict = {key + "." + k: v for k, v in nested_projects.items()}
                projects = {
                    **projects,
                    **nested_dict,
                }
            elif nested_values:
                projects[key] = nested_values
            else:
                projects[key] = nested_projects
        else:
            values[key] = value
    return (projects, values)


def get_projects(gh_configs):
    projects, values = recurs_projects(gh_configs)
    return projects


def main():
    if len(sys.argv) > 1:
        for config_file in sys.argv[1:]:
            with open(config_file, "rb") as f:
                config = tomli.load(f)
            if "gh" in config:
                gh_config = config["gh"]
                outdir = gh_config.get("outdir", "")
                projects = get_projects(gh_config)
                failed = run(projects, outdir, gh_config.get("count", 1))
            else:
                print(f"{config_file}: nothing to do", file=os.stderr)


if __name__ == "__main__":
    main()
