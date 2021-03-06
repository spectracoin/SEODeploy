#! /usr/bin/env python
# coding: utf-8
#
# Copyright (c) 2020 JR Oakes
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Helper functions for SEODeploy module."""

from urllib.parse import urlsplit
from types import SimpleNamespace
from functools import reduce
import json
import re

import multiprocessing as mp
import numpy as np

from seodeploy.lib.config import Config

CONFIG = Config()


# Interable grouping function
def group_batcher(iterator, result, count, fill=0):

    """Given and iterator, returns batched results based on count.

    Parameters
    ----------
    iterator: list or tuple
        Iterable object
    result: type
        The `type` of the results to be returned.
    count: int
        How many in each Group.
    fill: str, int, float, or None
        Fill overflow with this value. If None, no fill is performed.

    Returns
    -------
    Generator
    """

    itr = iter(iterator)
    grps = -(-len(iterator) // count)
    rem = len(iterator) % count

    for i in range(grps):
        num = rem if not fill and rem and i + 1 == grps else count
        yield result([next(itr, fill) for i in range(num)])


# Multiprocessing functions
def _map(args):
    """Mapping helper function for mp_list_map."""
    lst, fnc, kwargs = args
    return fnc(list(lst), **kwargs)


def mp_list_map(lst, fnc, **kwargs):
    """Applies a function to a list by multiprocessing.

    Uses `max_threads` from `seodeploy_config.yaml` to determine whether to apply
    function by multiprocessing.  if max_threads > 1 , then multiprocessing is used.

    Parameters
    ----------
    lst: list
        Iterable object
    fnc: function
        A function to map to all list values.
    kwargs: dict
        keyword parameters to supply to your function.

    Returns
    -------
    list
        List of data updated by function.
    """
    threads = CONFIG.MAX_THREADS

    if threads > 1:
        print("Running on {} threads.".format(str(threads)))
        pool = mp.Pool(processes=threads)
        result = pool.map(
            _map, [(l, fnc, kwargs) for l in np.array_split(lst, threads)]
        )
        pool.close()

        return list(np.concatenate(result))

    return _map((lst, fnc, kwargs))


def url_to_path(url):
    """Cleans a URL to only the path."""
    parts = urlsplit(url)
    return parts.path if not parts.query else parts.path + "?" + parts.query


def list_to_dict(lst, key):
    """Given a list of dicts, returns a dict where remaining values refereced by key."""
    result = {}
    for i in lst:
        result[i.pop(key)] = i
    return result


def dot_set(data):
    """Transforms a dictionary to be indexable by dot notation."""
    return (
        SimpleNamespace(**{k: dot_set(v) for k, v in data.items()})
        if isinstance(data, dict)
        else data
    )


def dot_get(dot_not, data):
    """Transforms a dictionary to be indexable by dot notation."""
    try:
        return reduce(dict.get, dot_not.split("."), data)
    except TypeError:
        return None


def to_dot(data):
    """Returns a list of dot notations for non-dict values in a dict."""

    def iter_dot(data, parent, result):
        if isinstance(data, dict):
            for k, v in data.items():
                if not isinstance(v, dict):
                    result.append(parent + [k])
                iter_dot(v, parent + [k], result)

        return result

    return [".".join(x) for x in iter_dot(data, [], [])]


def process_page_data(sample_paths, prod_result, stage_result, module_config):

    """Reviews the returned results for errors and formats result.

    Parameters
    ----------
    sample_paths: list
        List of Paths.
    prod_results: list
        List of prod data dictionaries.
        Fmt: [{'path': '/', 'page_data':{}, 'error': None}, ...]
    stage_result: list
        List of stage data dictionaries.
        Fmt: [{'path': '/', 'page_data':{}, 'error': None}, ...]
    module_config: Config
        Module config.

    Returns
    -------
    dict
        Dictionary in format:
        {'<path>':{'prod': <prod url data>, 'stage': <stage url data>, 'error': error},
        ...
        }
    """

    result = {}

    prod_data = list_to_dict(prod_result.copy(), "path")
    stage_data = list_to_dict(stage_result.copy(), "path")

    for path in sample_paths:
        error = prod_data[path]["error"] or stage_data[path]["error"]

        stg_page_data = maybe_replace_staging(
            stage_data[path]["page_data"], module_config
        )
        prod_page_data = prod_data[path]["page_data"]

        result[path] = {"prod": prod_page_data, "stage": stg_page_data, "error": error}

    return result


def maybe_replace_staging(page_data, module_config):
    """Replace host in JSON data if configured."""

    if module_config.replace_staging_host:
        json_data = json.dumps(page_data)
        json_data = re.sub(
            re.escape(module_config.stage_host), module_config.prod_host, json_data
        )
        return json.loads(json_data)

    return page_data
