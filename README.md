# quickstatements3

Repository for the development of a version 3 of the [QuickStatements](https://www.wikidata.org/wiki/Help:QuickStatements) tool for making bulk edits to [Wikidata](https://www.wikidata.org).

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

Alternatively, define that environment varibale inside the container shell and run the tests directly with `python3 manage.py test integration`.

### Custom Authorization Servers

If you want to use QuickStatements for a deploy that is completely independent form wikidata.org, (e.g, you are running your own [deployment of wikibase](https://wikiba.se/)) you will need to customize the following environment variables:

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
   webservice python3.11 shell -- ./www/python/venv/bin/python ./www/python/src/manage.py migrate
   webservice python3.11 shell -- ./www/python/venv/bin/python ./www/python/src/manage.py collectstatic --noinput
   ```
7. Start your webservice: `webservice python3.11 start`
8. Logs are at `~/uwsgi.log`

> **Note**: When using `toolforge webservice` or `webservice` commands, the specified commands run in a separate container. Alternatively, you can execute `webservice python3.11 shell` to run the bootstrap, migrate, and collectstatic commands interactively within a single container, reserving the (re)start step for a separate execution.
