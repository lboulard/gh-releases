#!/usr/bin/env python3

import json
import logging
import os
import os.path
import sys

import click
import requests
import tomli
from github import Auth, Github
from github.GithubException import (
    BadCredentialsException,
    GithubException,
    RateLimitExceededException,
    TwoFactorException,
)

from .model import Asset, Release, ReleaseJsonEncoder
from .sha256 import Cache, get_sha256

# https://pygithub.readthedocs.io/en/latest/

DEBUG_HTTP = False
if DEBUG_HTTP:
    import logging
    from http.client import HTTPConnection

    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def make_checksums(name, releases, session=None, cache=None):
    for release in releases:
        title = release.title or release.tag
        for asset in release.assets:
            print(f"{name}: SHA256 {title} / {asset.name}")
            from_cache, size, sha256 = get_sha256(
                asset.url, session=session, cache=cache
            )
            if size != asset.size:
                print(
                    f"{name}: SHA256 {title} / {asset.name} size {size} != {asset.size} mismatch"
                )
            elif sha256:
                hint = " (no change)" if from_cache else ""
                asset.checksum = "sha256:" + sha256
                print(f"{name}: SHA256 {title} / {asset.name} sha256:{sha256}{hint}")


class GithubWorker:
    def __init__(self, access_token=None):
        auth = Auth.Token(access_token) if access_token else None
        self.g = Github(auth=auth)
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"token {access_token}"
        self.cache = Cache()

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
                    file=sys.stderr,
                )
                continue
            if len(releases) == count:
                break
        try:
            make_checksums(name, releases, session=self.session, cache=self.cache)
        finally:
            self.cache.commit()
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
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print(
            "**WARNING using GitHub as guest, please provide GITHUB_TOKEN", file=stderr
        )
    gw = GithubWorker(github_token)
    logging.info(f"cache path: {gw.cache.path}")
    for name, args in projects.items():
        output = name + ".json"
        if "output" in args:
            output = args["output"]
        if not output:
            print(f"{name}: ** ERROR missing output filename", file=stderr)
            failed = True
            continue
        if not "project" in args:
            print(f"{name}: * ERROR missing project name", file=stderr)
            failed = True
            continue
        output_path = os.path.join(outdir, output)
        count = args.get("count", count)
        print(f"{name}: ... getting {count} release{'s' if count > 1 else ''}")
        try:
            releases = gw.get_releases(name, args["project"], count)
        except (BadCredentialsException, TwoFactorException) as e:
            print("FATAL: GitHub API failed by raising unrecoverable exception")
            print(e)
            failed = True
            break
        except (GithubException, RateLimitExceededException) as e:
            print("ERROR: GitHub API failed by raising exception")
            print(e)
            continue
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
                projects = {**projects, **nested_dict}
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


@click.command()
@click.option("--select", "-f", multiple=True, help="only fetch this tool")
@click.argument("configs", nargs=-1, type=click.File("rb"))
@click.option(
    "--log-level",
    "--log",
    "-d",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    metavar="loglevel",
    help="set logging level",
)
def main(select, log_level, configs):
    #
    if log_level is not None:
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError("Invalid log level: %s" % log_level)
        logging.basicConfig(level=numeric_level)
    #
    for config_file in configs:
        config = tomli.load(config_file)
        if "gh" in config:
            gh_config = config["gh"]
            outdir = gh_config.get("outdir", "")
            projects = get_projects(gh_config)
            if select:
                projects = {k: p for k, p in projects.items() if k in select}
            failed = run(projects, outdir, gh_config.get("count", 1))
        else:
            print(f"{config_file}: nothing to do", file=sys.stderr)


if __name__ == "__main__":
    main()
