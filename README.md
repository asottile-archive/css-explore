[![Build Status](https://dev.azure.com/asottile/asottile/_apis/build/status/asottile.css-explore?branchName=master)](https://dev.azure.com/asottile/asottile/_build/latest?definitionId=42&branchName=master)
[![Azure DevOps coverage](https://img.shields.io/azure-devops/coverage/asottile/asottile/42/master.svg)](https://dev.azure.com/asottile/asottile/_build/latest?definitionId=42&branchName=master)

css-explore
===========

This originally started as a tool to visualize the parse tree of a css
document, but more or less turned into a pretty printer.

The reason I made this project was to compare compilation outputs of various
implementations of scss in an effort to switch a codebase from one compiler
to another.

This uses:
- [reworkcss/css](https://github.com/reworkcss/css) for parsing
- [ekalinin/nodeenv](https://github.com/ekalinin/nodeenv) for bootstrapping node


## Usage

```console
$ css-format --help
usage: css-format [-h] filename

positional arguments:
  filename

optional arguments:
  -h, --help  show this help message and exit
```

Example run:

```console
$ echo 'body{color:red}' > test.css
$ css-format test.css
body {
    color: red;
}
```
