# -*- coding: UTF-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals

import hashlib
import io
import os

import pytest

from css_explore import main


def test_indent():
    assert main.indent('foo\n    bar\n') == '    foo\n        bar\n'


def test_called_process_error():
    x = main.CalledProcessError(1, 'foo', 'bar')
    assert x.args == (
        'Unexpected returncode (1)\n'
        'stdout:\nfoo\n'
        'stderr:\nbar\n',
    )


def test_invalid_css():
    with pytest.raises(main.CalledProcessError):
        main.format_css('body {')


def test_format_css_simple():
    ret = main.format_css('body { color: #1e77d3; }')
    assert ret == (
        'body {\n'
        '    color: #1e77d3;\n'
        '}\n'
    )


def test_unicodez_format_css():
    ret = main.format_css("body { content: '☃'; }")
    assert ret == (
        'body {\n'
        "    content: '☃';\n"
        '}\n'
    )


def test_media_query():
    ret = main.format_css('@media print { body { color: red; } }')
    assert ret == (
        '@media print {\n'
        '    body {\n'
        '        color: red;\n'
        '    }\n'
        '}\n'
    )


def test_keyframes():
    ret = main.format_css(
        '@keyframes my-animation { 0% { opacity: 0; } 100% { opacity: 1; } }'
    )
    assert ret == (
        '@keyframes my-animation {\n'
        '    0% {\n'
        '        opacity: 0;\n'
        '    }\n'
        '    100% {\n'
        '        opacity: 1;\n'
        '    }\n'
        '}\n'
    )


def test_ignore_empty_rules():
    ret = main.format_css('a{}', ignore_empty_rules=True)
    assert ret == ''


def test_charset():
    ret = main.format_css('@charset "utf-8";')
    assert ret == '@charset "utf-8";\n'


def test_ignore_charset():
    ret = main.format_css('@charset "utf-8";', ignore_charset=True)
    assert ret == ''


def test_normalize_color():
    ret = main.format_css('a{color: rgba(255,255,255,0.7);}')
    assert ret == (
        'a {\n'
        '    color: rgba(255, 255, 255, 0.7);\n'
        '}\n'
    )


def test_normalize_comma():
    ret = main.format_css(
        'a{box-shadow: 0 1px 1px #fff,inset 0 4px 4px #000;}'
    )
    assert ret == (
        'a {\n'
        '    box-shadow: 0 1px 1px #fff, inset 0 4px 4px #000;\n'
        '}\n'
    )


def test_normalize_child_selector():
    ret = main.format_css('a>b{color: red;}')
    assert ret == (
        'a > b {\n'
        '    color: red;\n'
        '}\n'
    )


def test_normalize_child_selector_more():
    ret = main.format_css('a > b { color: red; }')
    assert ret == (
        'a > b {\n'
        '    color: red;\n'
        '}\n'
    )


def test_normalize_comma_media_query():
    ret = main.format_css(
        '@media (min-device-pixel-ratio: 2),(min-resolution: 192dpi) {'
        '    a { color: red; }'
        '}'
    )
    assert ret == (
        '@media (min-device-pixel-ratio: 2), (min-resolution: 192dpi) {\n'
        '    a {\n'
        '        color: red;\n'
        '    }\n'
        '}\n'
    )


def test_normalize_unicode_escapes():
    ret = main.format_css(r"a{content: '\25AA'}")
    assert ret == (
        'a {\n'
        "    content: '▪';\n"
        '}\n'
    )


def test_normalize_unicode_escapes_more():
    ret = main.format_css(r"a{content: '\2014 \00A0';}")
    assert ret == (
        'a {\n'
        "    content: '\u2014\u00A0';\n"
        '}\n'
    )


def test_normalize_font_shorthand():
    ret = main.format_css('a {font: 12px/1.2 Arial}')
    assert ret == (
        'a {\n'
        '    font: 12px / 1.2 Arial;\n'
        '}\n'
    )


def test_normalize_less_than_one_float():
    ret = main.format_css('a {opacity: .35}')
    assert ret == (
        'a {\n'
        '    opacity: 0.35;\n'
        '}\n'
    )


def test_normalize_selector_order():
    ret = main.format_css('b, a, c { color: red; }')
    assert ret == (
        'a, b, c {\n'
        '    color: red;\n'
        '}\n'
    )


def test_normalize_selector_order_after():
    ret = main.format_css('a>b, a > b.c { color: red; }')
    assert ret == (
        'a > b, a > b.c {\n'
        '    color: red;\n'
        '}\n'
    )


def test_comments():
    ret = main.format_css('/*hi*/')
    assert ret == '/*hi*/\n'


def test_ignore_comments():
    ret = main.format_css('/*hi*/', ignore_comments=True)
    assert ret == ''


def test_urls():
    ret = main.format_css('a { background: url(//a/b/c); }')
    assert ret == (
        'a {\n'
        '    background: url(//a/b/c);\n'
        '}\n'
    )


def test_normalize_multiple_spaces():
    ret = main.format_css('a { background-position: 0    0; }')
    assert ret == (
        'a {\n'
        '    background-position: 0 0;\n'
        '}\n'
    )


def test_normalize_colors():
    ret = main.format_css('a { color: #223344; }')
    assert ret == (
        'a {\n'
        '    color: #234;\n'
        '}\n'
    )


def test_normalize_pixels():
    ret = main.format_css('a { width: 3.0px; }')
    assert ret == (
        'a {\n'
        '    width: 3px;\n'
        '}\n'
    )


def test_normalize_quotes():
    ret = main.format_css('a { content: "foo"; }')
    assert ret == (
        'a {\n'
        "    content: 'foo';\n"
        '}\n'
    )


def test_normalize_quotes_ignores_strings_containing_quotes():
    # These are hard, let's leave them alone for now
    ret = main.format_css('a { content: "\'"; }')
    assert ret == (
        'a {\n'
        '    content: "\'";\n'
        '}\n'
    )


def test_normalize_black():
    # Why black is special, shrugs
    ret = main.format_css('a { border-top: 1px solid black; }')
    assert ret == (
        'a {\n'
        '    border-top: 1px solid #000;\n'
        '}\n'
    )


def test_document():
    ret = main.format_css(
        '@-moz-document url-prefix() { a { color: red; } }'
    )
    assert ret == (
        '@-moz-document url-prefix() {\n'
        '    a {\n'
        '        color: red;\n'
        '    }\n'
        '}\n'
    )


def test_supports():
    ret = main.format_css(
        '@supports (-moz-appearance:meterbar) { a { color: red; } }',
    )
    assert ret == (
        '@supports (-moz-appearance:meterbar) {\n'
        '    a {\n'
        '        color: red;\n'
        '    }\n'
        '}\n'
    )


def test_import():
    ret = main.format_css('@import url(//foo);')
    assert ret == '@import url(//foo);\n'


def test_buffer_bug():
    """A bug existed in the js code which was only triggered due to buffering
    issues.  This requires a large css file rich with unicode characters.
    """
    def md5(s):
        return hashlib.md5(s.encode('UTF-8')).hexdigest()

    css = 'a{b:' + 'Ｐゴシック' * 50000 + '}'
    orig = md5(main.format_css(css))

    for _ in range(5):
        assert md5(main.format_css(css)) == orig


@pytest.mark.usefixtures('in_tmpdir')
def test_require_nodeenv_not_there(check_call_mock):
    def make_if_not_exists(*_, **__):
        if not os.path.exists(main.NENV_PATH):
            os.mkdir(main.NENV_PATH)

    check_call_mock.side_effect = make_if_not_exists
    main.require_nodeenv()
    assert check_call_mock.call_count == 2
    assert os.path.exists('{}/installed'.format(main.NENV_PATH))


@pytest.mark.usefixtures('in_tmpdir')
def test_require_nodeenv_already_there(check_call_mock):
    # Make it look like we've already installed
    os.mkdir(main.NENV_PATH)
    open('{}/installed'.format(main.NENV_PATH), 'w').close()

    # If an installation is attempted, it'll raise
    check_call_mock.side_effect = AssertionError
    main.require_nodeenv()


def test_main_integration(tmpdir, capsys):
    tmpfile = tmpdir.join('temp.css').strpath
    with io.open(tmpfile, 'w') as tmpfile_obj:
        tmpfile_obj.write('body { color: red; }')
    main.main([tmpfile])
    out, _ = capsys.readouterr()
    assert out == (
        'body {\n'
        '    color: red;\n'
        '}\n'
    )
