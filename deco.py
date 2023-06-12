#!/usr/bin/env python
# -*- coding: utf-8 -*-

from functools import wraps


def disable():
    """
    Disable a decorator by re-assigning the decorator's name
    to this function. For example, to turn off memoization:

    >>> memo = disable
    """

    return


def decorator(func):
    """
    Decorate a decorator so that it inherits the docstrings
    and stuff from the function it's decorating.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def countcalls(func):
    """Decorator that counts calls made to the function decorated."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.calls += 1
        return func(*args, **kwargs)

    wrapper.calls = 0

    return wrapper


def memo(func):
    """
    Memoize a function so that it caches all return values for
    faster future lookups.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if args in memo_map:
            return memo_map[args]

        result = func(*args, **kwargs)
        memo_map[args] = result

        return result

    memo_map = {}

    return wrapper


def n_ary(func):
    """
    Given binary function f(x, y), return an n_ary function such
    that f(x, y, z) = f(x, f(y,z)), etc. Also allow f(x) = x.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if len(args) > 2:
            result = func(*args[len(args) - 2 :], **kwargs)
            for arg in args[: len(args) - 2][::-1]:
                result = func(arg, result)
        else:
            result = func(*args, **kwargs)

        return result

    return wrapper


def trace(trace_string):
    """Trace calls made to function decorated.

    @trace("____")
    def fib(n):
        ....

    >>> fib(3)
     --> fib(3)
    ____ --> fib(2)
    ________ --> fib(1)
    ________ <-- fib(1) == 1
    ________ --> fib(0)
    ________ <-- fib(0) == 1
    ____ <-- fib(2) == 2
    ____ --> fib(1)
    ____ <-- fib(1) == 1
     <-- fib(3) == 3

    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            wrapper.calls += 1
            wrapper.trace += f"{trace_string * (wrapper.calls - 1)} --> {func.__name__}({args[0]})\n"

            result = func(*args, **kwargs)

            wrapper.trace += f"{trace_string * (wrapper.calls - 1)} <-- {func.__name__}({args[0]}) == {result}\n"
            wrapper.calls -= 1

            if not wrapper.calls:
                print(wrapper.trace)

            return result

        wrapper.calls = 0
        wrapper.trace = ""

        return wrapper

    return decorator


@countcalls
@memo
@n_ary
def foo(a, b):
    return a + b


@countcalls
@memo
@n_ary
def bar(a, b):
    return a * b


@countcalls
@trace("####")
@memo
def fib(n):
    """Some doc"""
    return 1 if n <= 1 else fib(n - 1) + fib(n - 2)


def main():
    print(foo(4, 3))
    print(foo(4, 3, 2))
    print(foo(4, 3))
    print("foo was called", foo.calls, "times")

    print(bar(4, 3))
    print(bar(4, 3, 2))
    print(bar(4, 3, 2, 1))
    print("bar was called", bar.calls, "times")

    print(fib.__doc__)
    fib(3)
    print(fib.calls, "calls made")


if __name__ == "__main__":
    main()
