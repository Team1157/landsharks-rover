import logging
import typing as t

# Numeric logging levels as defined by `logging`
LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "fatal": logging.FATAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "warn": logging.WARN,
    "info": logging.INFO,
    "debug": logging.DEBUG
}


def flatten_dict(tree: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """
    Takes a multi-level dictionary and flattens it into one layer, with keys representing the path to the value in the
    original dictionary
    :param tree: The dictionary to flatten
    :return: The flattened dictionary
    """
    out = {}
    for key, value in tree.items():
        if type(value) == dict:
            for k, v in flatten_dict(value).items():
                out[f"{key}.{k}"] = v
        else:
            out[key] = value
    return out