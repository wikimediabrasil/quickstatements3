# QuickStatements 3.0

QuickStatements is a tool for making bulk edits to [Wikidata](https://www.wikidata.org) and other [Wikibase](https://wikiba.se/) instances: write a list of commands (or upload a CSV file), preview them, and let QuickStatements run them as edits for you.

This repository contains version 3.0, a rewrite of [QuickStatements 2](https://www.wikidata.org/wiki/Help:QuickStatements) developed by [Wikimedia Brasil](https://meta.wikimedia.org/wiki/Wikimedia_Brasil).

**Useful links:**

* 🚀 **Use it:** <https://qs-dev.toolforge.org/>
* 📰 [Project page and timeline](https://meta.wikimedia.org/wiki/QuickStatements_3.0) on meta.wikimedia.org
* 📖 [Documentation](https://meta.wikimedia.org/wiki/QuickStatements_3.0/Documentation) and [user guide](https://meta.wikimedia.org/wiki/QuickStatements_3.0/Documentation/User_guide) on meta.wikimedia.org
* 🎬 [Launch video](https://commons.wikimedia.org/wiki/File:Wikidata_Lab_XLIV_-_QuickStatements_3.0.webm) (Wikidata Lab XLIV, February 2025)
* 🐞 [Report a bug or request a feature](https://github.com/wikimediabrasil/quickstatements3/issues) on GitHub
* 🌐 [Help translate the interface](https://translatewiki.net/wiki/Translating:Quickstatements3) on translatewiki.net

## Features

* Write commands in the **V1** syntax or upload a **CSV** file
* **Preview** a batch and see errors before running it
* Create and edit items and properties: statements, **qualifiers**, **references**, **ranks**, labels, descriptions, aliases and sitelinks
* Add or remove qualifiers and references while preserving the rest of the statement
* Optionally **combine** all commands for the same entity into a single edit
* Optionally **stop a batch** as soon as a command fails
* **Rerun** a batch or restart a stopped one
* Run several batches at the same time
* Works with **multiple Wikibase** instances
* Batch reports with items created, edits and errors, plus a [statistics page](https://qs-dev.toolforge.org/statistics/)
* [REST API](https://qs-dev.toolforge.org/api/docs) to create and follow batches programmatically
* Interface available in many languages

## Command formats

Both examples create a new item with an English label and description, add "instance of: human" (`P31`) and a date of birth (`P569`) with a reference (`S248`, "stated in").

**V1** (one command per line, columns separated by `|` or `TAB`; `LAST` refers to the item just created). The last line adds a statement with a qualifier (`P582`, "end time") to an existing item:

```
CREATE
LAST|Len|"Douglas Adams"
LAST|Den|"English writer and humorist"
LAST|P31|Q5
LAST|P569|+1952-03-11T00:00:00Z/11|S248|Q36578
```

**CSV** (one row per item; an empty `qid` creates a new item, and the header defines what each column means):

```csv
qid,Len,Den,P31,P569,S248
,Douglas Adams,English writer and humorist,Q5,+1952-03-11T00:00:00Z/11,Q36578
```

## Compared to QuickStatements 2

QuickStatements 3.0 keeps the familiar V1 and CSV command syntaxes, so existing commands can mostly be reused. The main differences are:

* It uses the new [Wikibase REST API](https://www.wikidata.org/wiki/Wikidata:REST_API) instead of the Action API.
* Commands for the same entity can be combined into one edit, which keeps item histories shorter.
* Qualifiers and references can be added or removed without replacing the whole statement, and ranks can be set.
* Batches are validated and previewed before running, with clearer error reports.
* Values are shown with localized labels, and dates and coordinates support custom calendars, precision and globes.

See the [documentation](https://meta.wikimedia.org/wiki/QuickStatements_3.0/Documentation/User_guide) for the full command reference.

# Development

## Local setup

Required tools:

* [Docker](https://docs.docker.com/engine/install/)
* [docker-compose](https://docs.docker.com/compose/install/)

To start the services, run:

```bash
docker-compose up --build
```

QuickStatements 3.0 will be available at <http://localhost:8000/>.

If you want to modify configurations, copy `.env.sample` into `.env` and modify the environment variables. The documentation for each environment variable is explained in `.env.sample`.

By default, QuickStatements 3.0 will target <https://test.wikidata.org/> as its default Wikibase.

To authenticate it locally, you will need to use the developer access. Request an access token at <https://api.wikimedia.org/wiki/Special:AppManagement>, click on "Create key". You should ask for a **Personal API token**, allow it to create and edit items and save. Copy the **Access token**. The access token can be used on <http://localhost:8000/auth/login/dev/> to log in.

### Admin access 

After logging in, you can give your user access to the admin panel at <http://localhost:8000/admin/> by running:

```bash
docker-compose exec app python3 manage.py give_admin_access "username"
```

### Checking set up

To check your local set up you may go to <http://localhost:8000/batch/new/> and add a test batch on <https://test.wikidata.org>. For example, you may run the following v1 commands, which should create an item and add a statement to it:

```
CREATE
LAST|P65|42
```

## Wikibase server

QuickStatements 3.0 uses the Wikibase REST API provided in `/wikibase/v1`

You can define which wikibase you can connect to via the admin. There you will need to provide the following information:

 - URL of the server
 - Identifier (Any string that is unique to your set of servers)
 - OAuth Client ID & secret (see section below) if you will be using OAuth login. If you're using the developer access login, OAuth Client ID & secret are not needed.

## OAuth

This application uses OAuth2 with the Mediawiki provider (at www.wikidata.org)
You will probably need the following grants:

* Perform high volume activity
  * High-volume (bot) access
* Interact with pages
  * Edit existing pages
  * Edit protected pages (risk rating: vandalism)
  * Create, edit, and move pages

### Consumer

Register a consumer in <https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration>.

This application is listening on `/auth/callback/`, so, when registering, define the callback endpoint as `https://yourdomain.com/auth/callback/`.

After receiving the consumer id and secret, set up the `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` environment variables.

### Developer access

If you want to login with a developer access token, you need to register for yourself an owner-only consumer application for OAuth2. Follow the form and be sure to tick "This consumer is for use only by <YOUR USERNAME>".

### Integration tests

To run Integration tests on https://test.wikidata.org, you'll need a developer access token (owner-only) to edit on `test.wikidata.org`.

After obtaining it, define the environment variable `INTEGRATION_TEST_AUTH_TOKEN` in `.env` file as your developer access token. Then, run the tests with `make integration`.

Alternatively, define that environment variable inside the container shell and run the tests directly with `python3 manage.py test integration`.

### Custom Authorization Servers

If you want to use QuickStatements for a deploy that is completely independent from wikidata.org, (e.g, you are running your own [deployment of wikibase](https://wikiba.se/)) you will need to customize the following environment variables:

 - `OAUTH_AUTHORIZATION_SERVER` (Default: "https://www.wikidata.org")
 - `OAUTH_ACCESS_TOKEN_URL`     (Default: `OAUTH_AUTHORIZATION_SERVER`/w/rest.php/oauth2/access_token)
 - `OAUTH_AUTHORIZATION_URL`    (Default: `OAUTH_AUTHORIZATION_SERVER`/w/rest.php/oauth2/authorize)
 - `OAUTH_PROFILE_URL`          (Default: `OAUTH_AUTHORIZATION_SERVER`/w/rest.php/oauth2/resource/profile)

## Toolforge Deployment

1. Log in and enter into the tool user
2. Clone the repository at `~/www/python/`
3. Update `uwsgi.ini` with the tool name (in this case, it's `qs-dev`)
4. Create the environment variables file at `~/www/python/src/.env` with `install -m 600 /dev/null ~/www/python/src/.env` so that only your user can read it.
5. Create a database as in [Toolforge documentation](https://wikitech.wikimedia.org/wiki/Help:Toolforge/ToolsDB#Steps_to_create_a_user_database).
6. Initialize your webservice environment, database tables and static directory with:
   ```bash
   webservice python3.11 shell -- webservice-python-bootstrap
   webservice python3.11 shell -- ./www/python/venv/bin/pip install ./www/python
   webservice python3.11 shell -- ./www/python/venv/bin/python ./www/python/src/manage.py migrate
   webservice python3.11 shell -- ./www/python/venv/bin/python ./www/python/src/manage.py collectstatic --noinput
   ```
7. Start your webservice: `webservice python3.11 start`
8. Logs are at `~/uwsgi.log`

> **Note**: When using `toolforge webservice` or `webservice` commands, the specified commands run in a separate container. Alternatively, you can execute `webservice python3.11 shell` to run the bootstrap, migrate, and collectstatic commands interactively within a single container, reserving the (re)start step for a separate execution.
