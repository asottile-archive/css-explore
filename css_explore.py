import argparse
import json
import os.path
import re
import shlex
import subprocess
import sys
from typing import Any
from typing import Dict
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Type
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Protocol
else:
    Protocol = object

NENV_PATH = '.nenv-css-explore'
ACTIVATE = shlex.quote(f'{NENV_PATH}/bin/activate')
CSS_PROG = '''\
const css = require('css');
const fs = require('fs');

const src = fs.readFileSync('/dev/stdin').toString('UTF-8');
console.log(JSON.stringify(css.parse(src, {silent: false})));
'''


class CalledProcessError(ValueError):
    def __init__(self, returncode: int, out: str, err: str) -> None:
        super().__init__(
            f'Unexpected returncode ({returncode})\n'
            f'stdout:\n{out}\n'
            f'stderr:\n{err}\n',
        )


def _check_keys(d: Dict[str, Any], keys: Tuple[str, ...]) -> None:
    # All things have these keys
    keys = keys + ('position', 'type')
    assert set(d) <= set(keys), (set(d), set(keys))


def indent(text: str) -> str:
    lines = text.splitlines()
    return '\n'.join('    ' + line for line in lines) + '\n'


NUM = r'(\d*(?:\.\d*)?)'
HEXDIGIT = '[0-9a-fA-F]'

COLORS_TO_SHORT_COLORS = (
    ('black', '#000'),
    ('white', '#fff'),
)
COLOR_TO_SHORT_RE_PATTERN = r'\b{}\b'

COLOR_RE = re.compile(fr'#({HEXDIGIT})\1({HEXDIGIT})\2({HEXDIGIT})\3')
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
RGBA_RE = re.compile(fr'rgba\({NUM},\s*{NUM},\s*{NUM},\s*{NUM}\)')
RGBA_RE_SUB = r'rgba(\1, \2, \3, \4)'
SLASH_RE = re.compile(r'\s*/\s*')
SLASH_RE_SUB = ' / '
SPACES_RE = re.compile('[ ]+')
SPACES_RE_SUB = ' '


UNICODE_ESC_RE = re.compile(r'\\[A-Fa-f0-9]{4}\s*')


def norm_unicode_escapes(value: str) -> str:
    matches = UNICODE_ESC_RE.findall(value)
    for match in matches:
        value = value.replace(match, chr(int(match[1:].rstrip(), 16)))
    return value


class Settings(NamedTuple):
    ignore_charset: bool = False
    ignore_comments: bool = False
    ignore_empty_rules: bool = False


class CSSNode(Protocol):
    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'CSSNode': ...
    def to_text(self, settings: Settings) -> str: ...


class Property(NamedTuple):
    name: str
    value: str

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'Property':
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

    def to_text(self, settings: Settings) -> str:
        return f'    {self.name}: {self.value};\n'


class Charset(NamedTuple):
    charset: str

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'Charset':
        _check_keys(dct, ('charset',))
        return cls(dct['charset'])

    def to_text(self, settings: Settings) -> str:
        if settings.ignore_charset:
            return ''
        else:
            return f'@charset {self.charset};\n'


class Comment(NamedTuple):
    comment: str

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'Comment':
        _check_keys(dct, ('comment',))
        return cls(dct['comment'])

    def to_text(self, settings: Settings) -> str:
        if settings.ignore_comments:
            return ''
        else:
            return f'/*{self.comment}*/\n'


class Document(NamedTuple):
    vendor: str
    name: str
    rules: Tuple[CSSNode, ...]

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'Document':
        _check_keys(dct, ('vendor', 'document', 'rules'))
        rules = tuple(generic_to_node(node_dict) for node_dict in dct['rules'])
        return cls(dct.get('vendor', ''), dct['document'], rules)

    def to_text(self, settings: Settings) -> str:
        return '@{}document {} {{\n{}}}\n'.format(
            self.vendor,
            self.name,
            indent(''.join(rule.to_text(settings) for rule in self.rules)),
        )


class Import(NamedTuple):
    value: str

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'Import':
        _check_keys(dct, ('import',))
        return cls(dct['import'])

    def to_text(self, settings: Settings) -> str:
        return f'@import {self.value};\n'


class KeyFrame(NamedTuple):
    values: str
    properties: Tuple[Property, ...]

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'KeyFrame':
        _check_keys(dct, ('declarations', 'values'))
        properties = tuple(
            Property.from_dict(property_dict)
            for property_dict in dct['declarations']
        )
        return cls(', '.join(dct['values']), properties)

    def to_text(self, settings: Settings) -> str:
        return '{} {{\n{}}}\n'.format(
            self.values,
            ''.join(prop.to_text(settings) for prop in self.properties),
        )


class KeyFrames(NamedTuple):
    vendor: str
    name: str
    keyframes: Tuple[KeyFrame, ...]

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'KeyFrames':
        _check_keys(dct, ('vendor', 'name', 'keyframes'))
        keyframes = tuple(
            KeyFrame.from_dict(keyframe_dict)
            for keyframe_dict in dct['keyframes']
        )
        return cls(dct.get('vendor', ''), dct['name'], keyframes)

    def to_text(self, settings: Settings) -> str:
        return '@{}keyframes {} {{\n{}}}\n'.format(
            self.vendor,
            self.name,
            indent(
                ''.join(
                    keyframe.to_text(settings) for keyframe in self.keyframes
                ),
            ),
        )


class MediaQuery(NamedTuple):
    media: str
    rules: Tuple[CSSNode, ...]

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'MediaQuery':
        _check_keys(dct, ('media', 'rules'))
        media = dct['media']
        media = COMMA_RE.sub(COMMA_RE_SUB, media)
        rules = tuple(generic_to_node(node_dict) for node_dict in dct['rules'])
        return cls(media, rules)

    def to_text(self, settings: Settings) -> str:
        return '@media {} {{\n{}}}\n'.format(
            self.media,
            indent(''.join(rule.to_text(settings) for rule in self.rules)),
        )


class Rule(NamedTuple):
    selectors: str
    properties: Tuple[Property, ...]

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'Rule':
        _check_keys(dct, ('selectors', 'declarations'))
        selectors = [
            RELATION_RE.sub(RELATION_RE_SUB, selector)
            for selector in dct['selectors']
        ]
        properties = tuple(
            Property.from_dict(property_dict)
            for property_dict in dct['declarations']
        )
        return cls(', '.join(sorted(selectors)), properties)

    def to_text(self, settings: Settings) -> str:
        if settings.ignore_empty_rules and not self.properties:
            return ''
        return '{} {{\n{}}}\n'.format(
            self.selectors,
            ''.join(prop.to_text(settings) for prop in self.properties),
        )


class Supports(NamedTuple):
    supports: str
    rules: Tuple[CSSNode, ...]

    @classmethod
    def from_dict(cls, dct: Dict[str, Any]) -> 'Supports':
        _check_keys(dct, ('supports', 'rules'))
        rules = tuple(generic_to_node(node_dict) for node_dict in dct['rules'])
        return cls(dct['supports'], rules)

    def to_text(self, settings: Settings) -> str:
        return '@supports {} {{\n{}}}\n'.format(
            self.supports,
            indent(''.join(rule.to_text(settings) for rule in self.rules)),
        )


def require_nodeenv() -> None:
    # Make it in the current directory, whatevs.
    if os.path.exists(os.path.join(NENV_PATH, 'installed')):
        return

    subprocess.check_call(
        (sys.executable, '-m', 'nodeenv', NENV_PATH, '--prebuilt'),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.check_call(
        ('bash', '-c', f'. {ACTIVATE} && npm install -g css'),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Atomically indicate we've installed
    open(f'{NENV_PATH}/installed', 'w').close()


TO_NODE_TYPES: Dict[str, Type[CSSNode]] = {
    'charset': Charset,
    'comment': Comment,
    'document': Document,
    'import': Import,
    'keyframes': KeyFrames,
    'media': MediaQuery,
    'rule': Rule,
    'supports': Supports,
}


def generic_to_node(node_dict: Dict[str, Any]) -> CSSNode:
    return TO_NODE_TYPES[node_dict['type']].from_dict(node_dict)


def format_css(
        contents: str,
        *,
        ignore_charset: bool = False,
        ignore_comments: bool = False,
        ignore_empty_rules: bool = False,
) -> str:
    require_nodeenv()

    proc = subprocess.Popen(
        ('sh', '-c', f'. {ACTIVATE} && node -e {shlex.quote(CSS_PROG)}'),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='UTF-8',
    )
    out, err = proc.communicate(contents)
    if proc.returncode:
        raise CalledProcessError(proc.returncode, out, err)

    sheet = json.loads(out)['stylesheet']
    rules = tuple(generic_to_node(rule_dict) for rule_dict in sheet['rules'])
    return ''.join(
        rule.to_text(
            Settings(
                ignore_charset=ignore_charset,
                ignore_comments=ignore_comments,
                ignore_empty_rules=ignore_empty_rules,
            ),
        )
        for rule in rules
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args(argv)
    contents = open(args.filename).read()
    print(format_css(contents).rstrip())
    return 0


if __name__ == '__main__':
    exit(main())
