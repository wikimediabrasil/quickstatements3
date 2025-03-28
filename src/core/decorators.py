def cache_with_first_arg(cache_name):
    """
    Returns a decorator that caches the value in a dictionary cache with `cache_name`,
    using as key the first argument of the method.

    If there is not first argument or first keyword argument, it uses a generic key.
    """

    def decorator(method):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, cache_name):
                setattr(self, cache_name, {})

            if len(args) >= 1:
                key = args[0]
            elif len(kwargs) >= 1:
                key = next(iter(kwargs.values()))
            else:
                key = "key"

            cache = getattr(self, cache_name)

            if cache.get(key) is not None:
                return cache.get(key)
            else:
                value = method(self, *args, **kwargs)
                cache[key] = value
                return value

        return wrapper

    return decorator
