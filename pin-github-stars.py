# Copyright (c) 2014 Bryan Dyck
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Adds starred GitHub repositories as bookmarks in Pinboard. All such bookmarks
will be tagged with 'github-star' and the project's language (if applicable).
The script will attempt to avoid overwriting bookmarks in Pinboard by checking
starred repos against the most recent bookmark with the 'github-star' tag.

Requires a GitHub OAuth token and a Pinboard API token, both of which may be
stored in ~/.github_oauth_token and ~/.pinboard_api_token respectively
instead of passing them as command-line options.

Dependencies:
    - Requests (http://docs.python-requests.org/en/latest/)
"""

import os
import re
import sys

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from time import sleep

import requests


GH_API = 'https://api.github.com'
PB_API = 'https://api.pinboard.in/v1'
SLEEP_TIME = 3
MAX_RETRIES = 10


def add_bookmark(gh_data, pb_api_token):
    """
    Adds a bookmark to Pinboard.

    GitHub -> Pinboard field mapping:

    full_name   -> description
    html_url    -> url
    description -> extended
    language    -> tags
    """
    description = gh_data['description']
    if gh_data['homepage']:
        description += '\n\nProject homepage: {}'.format(gh_data['homepage'])
    tags = 'github-star'
    if gh_data['language']:
        tags = ' '.join((tags, gh_data['language'].lower()))
    params = {'description': gh_data['full_name'],
              'url': gh_data['html_url'],
              'extended': description,
              'tags': tags,
              'replace': 'no',
              'auth_token': pb_api_token,
              'format': 'json'}
    r = requests.get('{}/posts/add'.format(PB_API),
                     params=params,
                     headers={'user-agent': 'pin-github-stars.py'})
    return r.json(), r.status_code


def get_most_recent_bookmark(pb_api_token):
    """
    Returns the most recent bookmark with the tag 'github-star', if any.
    """
    params = {'tag': 'github-star',
              'count': 1,
              'auth_token': pb_api_token,
              'format': 'json'}
    r = requests.get('{}/posts/recent'.format(PB_API),
                     params=params)
    return (r.json()['posts'] or None)


def get_github_stars(headers, sort_dir):
    """
    A generator that returns successive pages of a user's list of starred repos.
    """
    page = 1
    last = 1
    params = {'direction': sort_dir}
    while page <= last:
        params['page'] = page
        r = requests.get('{}/user/starred'.format(GH_API),
                         params=params,
                         headers=headers)
        yield r.json(), r.status_code
        if 'link' in r.headers:
            m = re.search(r'page=(\d+)>; rel="next",.*page=(\d+)>; rel="last"', r.headers['link'])
            if m is None:  # Lazy way to see if we hit the last page, which only has 'first' and 'prev' links
                break
            page, last = m.groups()


def filter_stars(stars, full_name):
    """
    Searches the list of starred repos and returns a truncated list if the
    specified repo is found in the list.
    """
    for i in xrange(len(stars)):
        if stars[i]['full_name'].lower() == full_name.lower():
            return stars[:i], True
    return stars, False


def exit_with_error(msg):
    print >>sys.stderr, '[ERROR] {}'.format(msg)
    sys.exit(1)


def load_token(filename):
    token = None
    if os.path.exists(os.path.expanduser(filename)):
        with open(os.path.expanduser(filename)) as f:
            token = f.readline().strip()
    return token


def main():
    arg_parser = ArgumentParser(description=__doc__,
                                formatter_class=RawDescriptionHelpFormatter)
    arg_parser.add_argument('-g',
                            '--github-token',
                            help='GitHub OAuth API token')
    arg_parser.add_argument('-p',
                            '--pinboard-token',
                            help='Pinboard API token')
    arg_parser.add_argument('-u',
                            '--github-user',
                            required=True,
                            help='GitHub username (sent as user-agent for API requests)')
    args = arg_parser.parse_args()

    gh_api_token = args.github_token or load_token('~/.github_oauth_token')
    pb_api_token = args.pinboard_token or load_token('~/.pinboard_api_token')

    if gh_api_token is None:
        exit_with_error('Could not load GitHub OAuth token')

    if pb_api_token is None:
        exit_with_error('Could not load Pinboard API token')

    gh_headers = {'authorization': 'token {}'.format(gh_api_token),
                  'accept': 'application/vnd.github.v3+json',
                  'user-agent': args.github_user}

    # Note: on first run (ie. we've never added starred repos to Pinboard),
    # flip the sort direction of the results from GitHub so that bookmarks
    # are added in chronological order (ie. when first run is complete,
    # the last bookmark added will be the most recent star).
    #
    # On subsequent runs, we query Pinboard for the most recently added
    # bookmark with a specific tag and use that to filter the list of
    # stars from GitHub.
    sort_dir = 'desc'
    most_recent = get_most_recent_bookmark(pb_api_token)
    hit_most_recent = False
    if most_recent is not None:
        most_recent = most_recent[0]['description']
    else:
        sort_dir = 'asc'

    print '[INFO] GitHub: Getting starred repos ...'
    for result, status in get_github_stars(gh_headers, sort_dir):
        if status != 200:
            exit_with_error('GitHub: {}'.format(result))
        if most_recent is not None:
            result, hit_most_recent = filter_stars(result, most_recent)
        for star in result:
            print '[INFO] Pinboard: Adding {} ...'.format(star['full_name'])
            r, s = add_bookmark(star, pb_api_token)
            retry = 1
            while s == 429 and retry <= MAX_RETRIES:
                print '[WARN] Pinboard: Rate-limited! Retrying ...'
                # Back off & retry
                sleep(SLEEP_TIME * retry)
                r, s = add_bookmark(star, pb_api_token)
                if r['result_code'].lower() != 'done':
                    exit_with_error('Pinboard: {}.'.format(r['result_code']))
                retry += 1
            else:
                if r['result_code'].lower() != 'done':
                    print '[WARN] Pinboard: {}.'.format(r['result_code'])
                sleep(SLEEP_TIME)
        if hit_most_recent:
            sys.exit(0)


if __name__ == '__main__':
    main()
