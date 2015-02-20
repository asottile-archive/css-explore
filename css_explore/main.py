from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import collections
import io
import os.path
import re
import string
import subprocess
import sys

import pkg_resources
import simplejson
import six


NENV_PATH = '.nenv-css-explore'


class CalledProcessError(ValueError):
    def __init__(self, returncode, out, err):
        super(CalledProcessError, self).__init__(
            'Unexpected returncode ({0})\n'
            'stdout:\n{1}\n'
            'stderr:\n{2}\n'.format(returncode, out, err),
        )


def _check_keys(d, keys):
    # All things have these keys
    keys = keys + ('position', 'type')
    assert set(d) <= set(keys), (set(d), set(keys))


def indent(text):
    lines = text.splitlines()
    return '\n'.join('    ' + line for line in lines) + '\n'


COMMA_RE = re.compile(r'(,\s*)')
COMMA_RE_SUB = ', '
FLOAT_RE = re.compile(r'(?<!\d)(\.\d+)')
FLOAT_RE_SUB = r'0\1'
RELATION_RE = re.compile(r'\s*([+>])\s*')
RELATION_RE_SUB = r' \1 '
NUM = r'(\d*(?:\.\d*)?)'
RGBA_RE = re.compile(r'rgba\({0},\s*{0},\s*{0},\s*{0}\)'.format(NUM))
RGBA_RE_SUB = r'rgba(\1, \2, \3, \4)'
SLASH_RE = re.compile(r'\s*/\s*')
SLASH_RE_SUB = ' / '


def norm_unicode_escapes(value):
    if (
            len(value) != len(r'"\0000"') or
            value[0] != value[-1] or
            value[0] not in ('"', "'") or
            value[1] != '\\' or
            not set(value[2:-1]) < set(string.hexdigits)
    ):
        return value

    quote_type = value[0]
    unescaped = six.unichr(int(value[2:-1], 16))
    return quote_type + unescaped + quote_type


class Property(collections.namedtuple('Property', ('name', 'value'))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        assert dct['type'] == 'declaration', dct['type']
        _check_keys(dct, ('property', 'value'))
        value = dct['value']
        value = COMMA_RE.sub(COMMA_RE_SUB, value)
        value = FLOAT_RE.sub(FLOAT_RE_SUB, value)
        value = RGBA_RE.sub(RGBA_RE_SUB, value)
        value = SLASH_RE.sub(SLASH_RE_SUB, value)
        value = norm_unicode_escapes(value)
        return cls(dct['property'], value)

    def to_text(self, **_):
        return '    {0}: {1};\n'.format(self.name, self.value)


class Charset(collections.namedtuple('Charset', ('charset',))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('charset',))
        return cls(dct['charset'])

    def to_text(self, **kwargs):
        ignore_charset = kwargs['ignore_charset']
        if ignore_charset:
            return ''
        else:
            return '@charset {0};\n'.format(self.charset)


class KeyFrame(collections.namedtuple('KeyFrame', ('values', 'properties'))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('declarations', 'values'))
        properties = tuple(
            Property.from_dict(property_dict)
            for property_dict in dct['declarations']
        )
        return cls(', '.join(dct['values']), properties)

    def to_text(self, **kwargs):
        return '{0} {{\n{1}}}\n'.format(
            self.values,
            ''.join(
                property.to_text(**kwargs) for property in self.properties
            ),
        )


class KeyFrames(
        collections.namedtuple('KeyFrames', ('vendor', 'name', 'keyframes'))
):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('vendor', 'name', 'keyframes'))
        keyframes = tuple(
            KeyFrame.from_dict(keyframe_dict)
            for keyframe_dict in dct['keyframes']
        )
        return cls(dct.get('vendor', ''), dct['name'], keyframes)

    def to_text(self, **kwargs):
        return '@{0}keyframes {1} {{\n{2}}}\n'.format(
            self.vendor,
            self.name,
            indent(''.join(
                keyframe.to_text(**kwargs) for keyframe in self.keyframes
            )),
        )


class MediaQuery(collections.namedtuple('MediaQuery', ('media', 'rules'))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('media', 'rules'))
        media = dct['media']
        media = COMMA_RE.sub(COMMA_RE_SUB, media)
        rules = tuple(generic_to_node(node_dict) for node_dict in dct['rules'])
        return cls(media, rules)

    def to_text(self, **kwargs):
        return '@media {0} {{\n{1}}}\n'.format(
            self.media,
            indent(''.join(rule.to_text(**kwargs) for rule in self.rules)),
        )


class Rule(collections.namedtuple('Rule', ('selectors', 'properties'))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('selectors', 'declarations'))
        selectors = ', '.join(dct['selectors'])
        selectors = RELATION_RE.sub(RELATION_RE_SUB, selectors)
        properties = tuple(
            Property.from_dict(property_dict)
            for property_dict in dct['declarations']
        )
        return cls(selectors, properties)

    def to_text(self, **kwargs):
        ignore_empty_rules = kwargs['ignore_empty_rules']
        if ignore_empty_rules and not self.properties:
            return ''
        return '{0} {{\n{1}}}\n'.format(
            self.selectors,
            ''.join(
                property.to_text(**kwargs) for property in self.properties
            ),
        )


def require_nodeenv():
    # Make it in the current directory, whatevs.
    if os.path.exists(os.path.join(NENV_PATH, 'installed')):
        return

    subprocess.check_call(
        (sys.executable, '-m', 'nodeenv', NENV_PATH, '--prebuilt'),
        stdout=open(os.devnull, 'w'),
        stderr=open(os.devnull, 'w'),
    )
    subprocess.check_call(
        ('{0}/bin/npm'.format(NENV_PATH), 'install', '-g', 'css'),
        stdout=open(os.devnull, 'w'),
        stderr=open(os.devnull, 'w'),
    )

    # Atomically indicate we've installed
    io.open('{0}/installed'.format(NENV_PATH), 'w').close()


TO_NODE_TYPES = {
    'charset': Charset,
    'keyframes': KeyFrames,
    'media': MediaQuery,
    'rule': Rule,
}


def generic_to_node(node_dict):
    return TO_NODE_TYPES[node_dict['type']].from_dict(node_dict)


def format_css(contents, **kwargs):
    ignore_charset = kwargs.pop('ignore_charset', False)
    ignore_empty_rules = kwargs.pop('ignore_empty_rules', False)
    assert not kwargs, kwargs
    require_nodeenv()

    proc = subprocess.Popen(
        (
            'sh', '-c',
            ". {0}/bin/activate && node '{1}'".format(
                NENV_PATH,
                pkg_resources.resource_filename(  # pylint:disable=no-member
                    'css_explore', 'resources/css_to_json.js',
                ),
            )
        ),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = proc.communicate(contents.encode('UTF-8'))
    out, err = out.decode('UTF-8'), err.decode('UTF-8')
    if proc.returncode:
        raise CalledProcessError(proc.returncode, out, err)

    sheet = simplejson.loads(out)['stylesheet']
    rules = tuple(generic_to_node(rule_dict) for rule_dict in sheet['rules'])
    return ''.join(
        rule.to_text(
            ignore_charset=ignore_charset,
            ignore_empty_rules=ignore_empty_rules,
        )
        for rule in rules
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args(argv)
    contents = io.open(args.filename).read()
    print(format_css(contents).rstrip())


if __name__ == '__main__':
    exit(main())
