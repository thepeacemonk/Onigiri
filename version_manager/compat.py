"""Tiny persistence adapter carried into older releases, without UI changes."""
import copy
from dataclasses import asdict, fields


def from_dict(cls, data):
    names = {field.name for field in fields(cls)}
    result = cls(**{key: value for key, value in data.items() if key in names})
    result._onigiri_extra = {key: copy.deepcopy(value) for key, value in data.items() if key not in names}
    return result


def payload(value):
    data = copy.deepcopy(getattr(value, "_onigiri_extra", {}))
    data.update(asdict(value))
    return data


def merge_payload(saved, current):
    data = copy.deepcopy(saved)
    for key, value in current.items():
        if isinstance(data.get(key), dict) and isinstance(value, dict):
            data[key] = merge_payload(data[key], value)
        else:
            data[key] = copy.deepcopy(value)
    return data
