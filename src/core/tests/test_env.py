import os


def test_environment_variables_are_not_set_to_real_servers():
    assert os.getenv("OAUTH_AUTHORIZATION_SERVER_URL") == "https://oauth.example.org"
    assert os.getenv("BASE_REST_URL") == "https://wikidata.example.org"
