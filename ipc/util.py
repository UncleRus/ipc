# -*- coding: utf-8 -*-


import functools
import threading


class AttrDict(dict):

    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


def detach(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.setDaemon(True)
    thread.start()

    return thread


def async_wrapper(func):
    def wrap(*args, **kwargs):
        detach(func, *args, **kwargs)

    return wrap


def channel(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)
    wrapped.channel = True

    return wrapped
