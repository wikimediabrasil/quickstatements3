# quickstatements3

Repository for the development of a version 3 of the [QuickStatements](https://www.wikidata.org/wiki/Help:QuickStatements) tool for making bulk edits to [Wikidata](https://www.wikidata.org).

## Local development HOW TO

Required tools:

* [Docker](https://docs.docker.com/engine/install/)
* [docker-compose](https://docs.docker.com/compose/install/)
* Make

To build the development container

```bash
> make build
```


Make sure that you have an env file inside the local etc/ dir.
This file contains all the **ENVIRONMENT VARIABLES** used by the system and must never be added to your git repo.

To generate a good secret key you can run with python 3.6+

```
python -c "import secrets; print(secrets.token_urlsafe())"
```

To start all services (database, web server, run a shell inside the container)

```bash
> make run
```


If everything is correct, **Quickstatements** will be available at http://localhost:8000/

If you are running this for the first time, you have to create a superuser for the Django admin. You can access the container with `make shell`. From there:

```bash
> django-admin createsuperuser
```

will run an interactive command which will ask you for your username, password, email, etc... follow the prompts and you should be able to login to the admin at `http://localhost:8000/admin`

## Wikibase server

QuickStatements 3.0 uses the Wikibase REST API to interact with a Wikibase server.
To define which server it is pointing to, define the `BASE_REST_URL` environment variable, pointing to the `rest.php` endpoint.
For example: `BASE_REST_URL=https://test.wikidata.org/w/rest.php`.

QuickStatements 3.0 uses the Wikibase REST API provided in `/wikibase/v1` and the profile endpoint for the Oauth2 API, provided in `/oauth2` to check autoconfirmation status and authorize users.

Currently it's only possible to point at one Wikibase instance.

## OAuth

This application uses OAuth2 with the Mediawiki provider.

The grants we probably need are:

* Perform high volume activity
  * High-volume (bot) access
* Interact with pages
  * Edit existing pages
  * Edit protected pages (risk rating: vandalism)
  * Create, edit, and move pages

### Consumer

After registering a consumer in

<https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration>

This application is listening on `/auth/callback/`, so, when registering, define the callback endpoint as `https://yourdomain.com/auth/callback/`.

After receiving the consumer id and secret, set up the `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET` environment variables.

### Developer access

If you want to login with a developer access token, you need to register for yourself an owner-only consumer application for OAuth2.
Follow the form and be sure to tick "This consumer is for use only by <YOUR USERNAME>".

### Integration tests

To run Integration tests on https://test.wikidata.org, you'll need a developer access token (owner-only) to edit on `test.wikidata.org`.

After obtaining it, define the environment variable `INTEGRATION_TEST_AUTH_TOKEN` in `etc/env` file as your developer access token.
Then, run the tests with `make integration`.

Alternatively, define that environment varibale inside the container shell and run the tests directly with `python3 manage.py test integration`.

## Toolforge Deployment

1. **Log In**: Access your Toolforge account and switch to your tool user by executing:
   ```bash
   become <your_tool_name>
   ```

2. **Clone the Repository**: Clone your project repository into `~/www/python` directory:
   ```bash
   git clone https://github.com/WikiMovimentoBrasil/quickstatements3 -C ~/www/python/
   ```

3. **Update Configuration**: Modify the `uwsgi.ini` file to include your tool name (e.g., `qs-dev`).

4. **Create Environment Variables File**: Set up the environment variables file at `~/www/python/src/.env` with restricted permissions, so that only your user can read it:
   ```bash
   install -m 600 /dev/null ~/www/python/src/.env
   ```

5. **Create a Database**: Follow the [Toolforge documentation](https://wikitech.wikimedia.org/wiki/Help:Toolforge/ToolsDB#Steps_to_create_a_user_database) to create a database for your tool.

6. **Bootstrap the Webservice Environment**: Initialize your webservice environment with the following command:
   ```bash
   webservice python3.11 shell -- webservice-python-bootstrap
   ```

7. **Apply Migrations**: Execute the necessary migrations for your application:
   ```bash
   webservice python3.11 shell -- '$HOME/www/python/venv/bin/python' '$HOME/www/python/src/manage.py' migrate
   ```

8. **Collect Static Assets**: Centralize your static files in the `STATIC_ROOT` directory by running:
   ```bash
   webservice python3.11 shell -- '$HOME/www/python/venv/bin/python' '$HOME/www/python/src/manage.py' collectstatic --noinput
   ```

9. **Start Your Webservice**: Make your tool available by starting the webservice:
   ```bash
   webservice python3.11 start
   ```

10. **Check Logs**: Access the logs at:
    ```bash
    ~/uwsgi.log
    ```

> **Note**: When using `toolforge webservice` or `webservice` commands, the specified commands run in a separate container. Alternatively, you can execute `webservice python3.11 shell` to run the bootstrap, migrate, and collectstatic commands interactively within a single container, reserving the (re)start step for a separate execution.
