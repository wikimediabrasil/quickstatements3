# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## Unreleased

### Added
 - `DEFAULT_WIKIBASE_URL` environment variables to set the wikibase (Default: 'https://wikidata.org')
 - `WHITELISTED_USERS` is a comma-separated list of usernames that
   will always be allowed to submit batches, even if not autoconfirmed (Default: empty list)
 - Running batches pause while the Wikibase server lag is above a threshold, following the
   [maxlag guidelines](https://www.mediawiki.org/wiki/Manual:Maxlag_parameter). The lag is read
   from the Action API, since the REST API has no `maxlag` parameter currently. Configured with
   `MAXLAG_PAUSE_ENABLED` (Default: `True`), `MAXLAG_THRESHOLD` in seconds (Default: `5`) and
   `MAXLAG_CHECK_INTERVAL` in seconds (Default: `15`, minimum `5`)

### Removed
 - `BASE_REST_URL` is no longer supported. Use `DEFAULT_WIKIBASE_URL` instead.
