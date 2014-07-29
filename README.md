# README

This script adds starred GitHub repositories as bookmarks in Pinboard. All such bookmarks will be tagged with `github-star` and the project's language (if applicable). The script will attempt to avoid overwriting bookmarks in Pinboard by checking starred repos against the most recent bookmark with the `github-star` tag.

The script requires a [GitHub personal API token](https://github.com/blog/1509-personal-api-tokens) (see note below) and a [Pinboard API token](https://pinboard.in/settings/password), both of which may be stored in files named `~/.github_oauth_token` and `~/.pinboard_api_token` respectively instead of passing them as command-line options. Dependencies are best installed with `pip` and `virtualenv`, though you're free to live on the edge and do things like `sudo easy_install requests` if you wish. Just don't say you weren't warned... :smirk:

Run `python pin-github-stars.py -h` for command-line help, which is an essentially abbreviated version of this README.

**Note:** Since your stars list is public information, a token for GitHub's API is not strictly necessary; however, it avoids issues with rate-limiting and unauthenticated API use. If you'd prefer not to create a token specifically for the script, feel free to fork it and remove the offending bits.

### Example usage

Passing everything on the command line would look like this:

```
$ python pin-github-stars.py -g 1234567890abcdef1234567890abcdef123456 -p pbuser:1234567890abcdef1234 -u github_user
```


### Dependencies

- [requests](http://docs.python-requests.org/en/latest/) >= 1.1.0
