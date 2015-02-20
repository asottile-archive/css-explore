[![Build Status](https://travis-ci.org/asottile/css-explore.svg?branch=master)](https://travis-ci.org/asottile/css-explore)
[![Coverage Status](https://img.shields.io/coveralls/asottile/css-explore.svg?branch=master)](https://coveralls.io/r/asottile/css-explore)

css-explore
==========

This originally started as a tool to visualize the parse tree of a css
document, but more or less turned into a pretty printer.

The reason I made this project was to compare compilation outputs of various
implementations of scss in an effort to switch a codebase from one compiler
to another.

## Usage

```
$ css-format --help
usage: css-format [-h] filename

positional arguments:
  filename

optional arguments:
  -h, --help  show this help message and exit
```

Example run:

```
$ echo 'body{color:red}' > test.css
$ css-format test.css
body {
    color: red;
}
```
