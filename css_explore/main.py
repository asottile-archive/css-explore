from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import collections
import io
import json
import os.path
import re
import subprocess
import sys

import pkg_resources
import six


NENV_PATH = '.nenv-css-explore'


class CalledProcessError(ValueError):
    def __init__(self, returncode, out, err):
        super(CalledProcessError, self).__init__(
            'Unexpected returncode ({})\n'
            'stdout:\n{}\n'
            'stderr:\n{}\n'.format(returncode, out, err),
        )


def _check_keys(d, keys):
    # All things have these keys
    keys = keys + ('position', 'type')
    assert set(d) <= set(keys), (set(d), set(keys))


def indent(text):
    lines = text.splitlines()
    return '\n'.join('    ' + line for line in lines) + '\n'


NUM = r'(\d*(?:\.\d*)?)'
HEXDIGIT = '[0-9a-fA-F]'

COLORS_TO_SHORT_COLORS = (
    ('black', '#000'),
    ('white', '#fff'),
)
COLOR_TO_SHORT_RE_PATTERN = r'\b{}\b'

COLOR_RE = re.compile(r'#({0})\1({0})\2({0})\3'.format(HEXDIGIT))
COLOR_RE_SUB = r'#\1\2\3'
COMMA_RE = re.compile(r'(,\s*)')
COMMA_RE_SUB = ', '
FLOAT_RE = re.compile(r'(?<!\d)(\.\d+)')
FLOAT_RE_SUB = r'0\1'
POINT_ZERO_RE = re.compile(r'(\d)\.0+px')
POINT_ZERO_SUB = r'\1px'
QUOTE_RE = re.compile(r'"([^\'"]*)"')
QUOTE_RE_SUB = r"'\1'"
RELATION_RE = re.compile(r'\s*([+>])\s*')
RELATION_RE_SUB = r' \1 '
RGBA_RE = re.compile(r'rgba\({0},\s*{0},\s*{0},\s*{0}\)'.format(NUM))
RGBA_RE_SUB = r'rgba(\1, \2, \3, \4)'
SLASH_RE = re.compile(r'\s*/\s*')
SLASH_RE_SUB = ' / '
SPACES_RE = re.compile('[ ]+')
SPACES_RE_SUB = ' '


UNICODE_ESC_RE = re.compile(r'\\[A-Fa-f0-9]{4}\s*')


def norm_unicode_escapes(value):
    matches = UNICODE_ESC_RE.findall(value)
    for match in matches:
        value = value.replace(match, six.unichr(int(match[1:].rstrip(), 16)))
    return value


class Property(collections.namedtuple('Property', ('name', 'value'))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        assert dct['type'] == 'declaration', dct['type']
        _check_keys(dct, ('property', 'value'))
        value = dct['value']
        value = COLOR_RE.sub(COLOR_RE_SUB, value)
        value = COMMA_RE.sub(COMMA_RE_SUB, value)
        value = FLOAT_RE.sub(FLOAT_RE_SUB, value)
        value = POINT_ZERO_RE.sub(POINT_ZERO_SUB, value)
        value = QUOTE_RE.sub(QUOTE_RE_SUB, value)
        value = RGBA_RE.sub(RGBA_RE_SUB, value)
        for color, replace in COLORS_TO_SHORT_COLORS:
            value = re.sub(
                COLOR_TO_SHORT_RE_PATTERN.format(color),
                replace,
                value,
            )
        # Only normalize slashes in font declarations for shorthand
        if dct['property'] == 'font':
            value = SLASH_RE.sub(SLASH_RE_SUB, value)
        value = SPACES_RE.sub(SPACES_RE_SUB, value)
        value = norm_unicode_escapes(value)
        return cls(dct['property'], value)

    def to_text(self, **_):
        return '    {}: {};\n'.format(self.name, self.value)


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
            return '@charset {};\n'.format(self.charset)


class Comment(collections.namedtuple('Comment', ('comment',))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('comment',))
        return cls(dct['comment'])

    def to_text(self, **kwargs):
        ignore_comments = kwargs['ignore_comments']
        if ignore_comments:
            return ''
        else:
            return '/*{}*/\n'.format(self.comment)


class Document(
        collections.namedtuple('Document', ('vendor', 'name', 'rules')),
):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('vendor', 'document', 'rules'))
        rules = tuple(generic_to_node(node_dict) for node_dict in dct['rules'])
        return cls(dct.get('vendor', ''), dct['document'], rules)

    def to_text(self, **kwargs):
        return '@{}document {} {{\n{}}}\n'.format(
            self.vendor,
            self.name,
            indent(''.join(rule.to_text(**kwargs) for rule in self.rules)),
        )


class Import(collections.namedtuple('Import', ('value',))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('import',))
        return cls(dct['import'])

    def to_text(self, **_):
        return '@import {};\n'.format(self.value)


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
        return '{} {{\n{}}}\n'.format(
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
        return '@{}keyframes {} {{\n{}}}\n'.format(
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
        return '@media {} {{\n{}}}\n'.format(
            self.media,
            indent(''.join(rule.to_text(**kwargs) for rule in self.rules)),
        )


class Rule(collections.namedtuple('Rule', ('selectors', 'properties'))):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('selectors', 'declarations'))
        selectors = [
            RELATION_RE.sub(RELATION_RE_SUB, selector)
            for selector in dct['selectors']
        ]
        selectors = ', '.join(sorted(selectors))
        properties = tuple(
            Property.from_dict(property_dict)
            for property_dict in dct['declarations']
        )
        return cls(selectors, properties)

    def to_text(self, **kwargs):
        ignore_empty_rules = kwargs['ignore_empty_rules']
        if ignore_empty_rules and not self.properties:
            return ''
        return '{} {{\n{}}}\n'.format(
            self.selectors,
            ''.join(
                property.to_text(**kwargs) for property in self.properties
            ),
        )


class Supports(
        collections.namedtuple('Supports', ('supports', 'rules')),
):
    __slots__ = ()

    @classmethod
    def from_dict(cls, dct):
        _check_keys(dct, ('supports', 'rules'))
        rules = tuple(generic_to_node(node_dict) for node_dict in dct['rules'])
        return cls(dct['supports'], rules)

    def to_text(self, **kwargs):
        return '@supports {} {{\n{}}}\n'.format(
            self.supports,
            indent(''.join(rule.to_text(**kwargs) for rule in self.rules)),
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
        (
            'bash', '-c',
            '. {}/bin/activate && npm install -g css'.format(NENV_PATH),
        ),
        stdout=open(os.devnull, 'w'),
        stderr=open(os.devnull, 'w'),
    )

    # Atomically indicate we've installed
    io.open('{}/installed'.format(NENV_PATH), 'w').close()


TO_NODE_TYPES = {
    'charset': Charset,
    'comment': Comment,
    'document': Document,
    'import': Import,
    'keyframes': KeyFrames,
    'media': MediaQuery,
    'rule': Rule,
    'supports': Supports,
}


def generic_to_node(node_dict):
    return TO_NODE_TYPES[node_dict['type']].from_dict(node_dict)


def format_css(contents, **kwargs):
    ignore_charset = kwargs.pop('ignore_charset', False)
    ignore_comments = kwargs.pop('ignore_comments', False)
    ignore_empty_rules = kwargs.pop('ignore_empty_rules', False)
    assert not kwargs, kwargs
    require_nodeenv()

    proc = subprocess.Popen(
        (
            'sh', '-c',
            ". {}/bin/activate && node '{}'".format(
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

    sheet = json.loads(out)['stylesheet']
    rules = tuple(generic_to_node(rule_dict) for rule_dict in sheet['rules'])
    return ''.join(
        rule.to_text(
            ignore_charset=ignore_charset,
            ignore_comments=ignore_comments,
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
