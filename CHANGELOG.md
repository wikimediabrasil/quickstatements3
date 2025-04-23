# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## Unreleased

### Added
 - `DEFAULT_WIKIBASE_URL` environment variables to set the wikibase (Default: 'https://wikidata.org')
 - `WHITELISTED_USERS` is a comma-separated list of usernames that
   will always be allowed to submit batches, even if not autoconfirmed (Default: empty list)

### Removed
 - `BASE_REST_URL` is no longer supported. Use `DEFAULT_WIKIBASE_URL` instead.
