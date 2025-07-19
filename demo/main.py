import time

from apollo.apollo_client import ApolloClient, _set_basic_logging


def main():
    _set_basic_logging()
    client = ApolloClient(
        app_id="fin-basic",
        config_url="http://apollo.leabyte.com:18080",
        secret="2b955246921f4d779fd566a2c8fd8d8b",
        use_scheduled_update=True,
        use_long_pool_update=True,
        change_listeners=[lambda e: print(e)],
    )
    client.start()
    config = client.get_config()
    print(config)
    config = client.get_value("infra.mongodb.uri")
    print(config)

if __name__ == "__main__":
    main()
    time.sleep(60 * 10)
