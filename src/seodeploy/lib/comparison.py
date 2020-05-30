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


from dictdiffer import diff

from .logging import get_logger
from .exceptions import StrategyNotImplemented, TypesMismatched

_LOG = get_logger(__name__)



class CompareDiffs():
    """Base strategy module. Strategy modules run comparative analysis on module content
    based on selected strategy.

    """

    def __init__(self):
        self.diffs = []


    def compare(self, path, item, d1, d2, tolerance=None):

        """ Parameters:
            -------------
            path: <str> the path compared.
            desc: <str> a description of the objects compared.
            d1: <list> or <dict> of items to compare (PROD)
            d2: <list> or <dict> of items to compare (STAGE)

            Optional
            -------------
            item: <str> Override the item name for each diff.
            tolerance: <float> For dictonaries with numeric values only, the percentage
                       to be considered a diff.
            element: <str> The key in a list of objects to group by. Default: element
            content: <str> The content in a list of objects to treat as the element's
                     content. Default: content

            Output
            -------------
            self.diffs = [{'module': <str>, 'path': <str>, 'item': <str>, 'diffs': [list]}, ...]

        """
        if type(d1) != type(d1):
            raise TypesMismatched('`d1` and `d2` must be the same type. Currently: {} and {}'.format(type(d1), type(d2)))
        elif isinstance(d1, dict):
            diffs = self.compare_objects(d1, d2, item=item, tolerance=tolerance)
        elif isinstance(d1, list) or isinstance(d1, set):
            diffs = self.compare_lists_of_objects(self, d1, d2, item=item, tolerance=tolerance)
        else:
            raise NotImplementedError('Only data of types `list`, `set`, or `dict` are supported.')

        self.add_diffs(path, diffs)


    def add_diffs(self, path, diffs):
        self.diffs.append({'path': path, 'diffs': diffs})


    def get_diffs(self):
        return self.diffs


    def compare_lists_of_objects(self, l1, l2, element='element', content='content',
                                 item=None, tolerance=None):

        # Changes list to dict based on given key_attr and content_attr values.
        d1, d2 = self._l2d(l1, l2, element, content)

        return self.compare_objects(d1, d2, item=item, tolerance=tolerance)


    def compare_objects(self, d1, d2, item=None, tolerance=None):

        tolerance = tolerance or 0

        if isinstance(d1, list) and isinstance(d2, list):
            otype = 'set'
            d1, d2 = set(d1), set(d2)
        elif isinstance(d1, set) and isinstance(d1, set):
            otype = 'set'
            pass
        elif isinstance(d1, dict) and isinstance(d1, dict):
            otype = 'dict'
        else:
            raise AttributeError('Unsupported object types provided.  Supports `list`, `set`, or `dict`')


        diffs = diff(d1, d2, tolerance=tolerance)

        return self.format_diffs(diffs, otype, item)


    @staticmethod
    def format_diffs(diffs, otype, item):

        results = []

        for diff in diffs:
            ctype, location, details = diff

            new = not location

            if ctype == "change":
                element = ".".join([str(i) for i in location]) if isinstance(location, list) else location
                item = item or location[0] if isinstance(location, list) else location
                results.append({'type': ctype, 'item': item, 'element': element, 'before': details[0], 'after': details[1]})
            else:
                for detail in details:

                    content = detail[1]

                    if otype == 'dict' and new:
                        element = '.'.join(detail[0]) if isinstance(detail[0], list) else detail[0]
                        item = item or detail[0]
                        content = detail[1][0]
                    elif otype == 'dict':
                        elements = ['.'.join([str(i) for i in location]) if isinstance(location, list) else str(location)]
                        elements += ['.'.join(detail[0]) if isinstance(detail[0], list) else str(detail[0])]
                        element = '.'.join(elements)
                        item = item or elements[0]
                        content = detail[1]
                    else:
                        item = ''.join(detail[1])
                        element = None
                        content = None

                    results.append({'type': ctype, 'item': item, 'element': element, 'content': content})

        return results


    @staticmethod
    def _l2d(l1, l2, key_attr, content_attr):
        """Turns a list of dicts into a dict based on given key attribute and content attribute.
            parameters:
                l1: <list> first list of dicts.
                l2: <list> second list of dicts.
                key_attr: <str> dict key to be used as key for new dict.
                content_attr: <str> or <list> dict key(s) to be used as value for new dict.
        """
        d1, d2 = {}, {}

        def adder(k, c, o):
            if k in o:
                o[k] += [c]
            else:
                o[k] = [c]

        if isinstance(content_attr, str):
            _ = [adder(i[key_attr], i[content_attr], d1) for i in l1 if key_attr in i and len(i[key_attr])]
            _ = [adder(i[key_attr], i[content_attr], d2) for i in l2 if key_attr in i and len(i[key_attr])]
        elif isinstance(content_attr, list):
            _ = [adder(i[key_attr], {i[v] for v in content_attr}, d1) for i in l1 if i[key_attr] and len(i[key_attr])]
            _ = [adder(i[key_attr], {i[v] for v in content_attr}, d2) for i in l2 if i[key_attr] and len(i[key_attr])]
        else:
            raise NotImplementedError("`content_attr` can only be of type `str` or `list`")


        return d1,d2