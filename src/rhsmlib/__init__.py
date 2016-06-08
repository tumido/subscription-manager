import importlib


def import_class(name):
    parts = name.split('.')
    mod = '.'.join(parts[:-1])
    mod = importlib.import_module(mod)
    return getattr(mod, parts[-1])
