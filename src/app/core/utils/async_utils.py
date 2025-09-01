import inspect


async def maybe_await(value):
    """Await value if it's awaitable; otherwise return it as-is.

    Useful in code paths where tests may monkeypatch async functions with
    regular mocks or direct values.
    """
    return await value if inspect.isawaitable(value) else value

