#!/usr/bin/env python3
"""Generate Nix.tmbundle — a TextMate 2 bundle for the Nix expression language.

Emits valid XML property lists via plistlib (no hand-escaping errors possible),
validates them by re-parsing, and sanity-compiles every regex.
Re-run to regenerate; UUIDs are kept stable below.
"""
import plistlib
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BUNDLE = ROOT / "Nix.tmbundle"

# Stable UUIDs (generated once; do not change on regeneration)
UUID_BUNDLE = "9A2D3C61-7E3B-4B5A-9C0F-2D6E8A1B4F70"
UUID_GRAMMAR = "5B1D9E22-4C8A-4F6E-B3A7-0E9D2C5F8A11"
UUID_COMMENTS = "C7F4A833-1D5B-4E29-A6C0-3B8E7D2F9A42"
UUID_PAIRS = "E1A6B944-8F2C-4D7A-B5E3-6C0D9F4A2B73"

# ---------------------------------------------------------------- grammar ---
# Character classes mirror Nix's own lexer (src/libexpr/lexer.l):
#   ID    [a-zA-Z_][a-zA-Z0-9_'-]*
#   PATH  [a-zA-Z0-9._+-]*(/[a-zA-Z0-9._+-]+)+/?
#   HPATH ~(/[a-zA-Z0-9._+-]+)+/?
#   SPATH <[a-zA-Z0-9._+-]+(/[a-zA-Z0-9._+-]+)*>
#   URI   [a-zA-Z][a-zA-Z0-9+.-]*:[a-zA-Z0-9%/?:@&=+$,_.!~*'-]+
GL = r"(?<![\w'.-])"   # left guard: not preceded by word char, ', ., -
GR = r"(?![\w'-])"     # right guard

grammar = {
    "name": "Nix",
    "scopeName": "source.nix",
    "fileTypes": ["nix"],
    "foldingStartMarker": r"(\{|\[|/\*)\s*$",
    "foldingStopMarker": r"^\s*(\}|\]|\*/)",
    "uuid": UUID_GRAMMAR,
    "patterns": [{"include": "#expression"}],
    "repository": {
        "expression": {
            "patterns": [
                {"include": "#comment"},
                {"include": "#string-indented"},
                {"include": "#string-quoted"},
                {"include": "#interpolation"},
                {"include": "#block-braces"},
                {"include": "#block-brackets"},
                {"include": "#block-parens"},
                {"include": "#keywords"},
                {"include": "#constants"},
                {"include": "#uri"},
                {"include": "#search-path"},
                {"include": "#path"},
                {"include": "#attribute-def"},
                {"include": "#builtins"},
                {"include": "#number"},
                {"include": "#function-param"},
                {"include": "#operators"},
                {"include": "#punctuation"},
            ]
        },
        "comment": {
            "patterns": [
                {
                    "name": "comment.block.nix",
                    "begin": r"/\*",
                    "end": r"\*/",
                    "beginCaptures": {"0": {"name": "punctuation.definition.comment.begin.nix"}},
                    "endCaptures": {"0": {"name": "punctuation.definition.comment.end.nix"}},
                },
                {
                    "name": "comment.line.number-sign.nix",
                    "match": r"(#).*$",
                    "captures": {"1": {"name": "punctuation.definition.comment.nix"}},
                },
            ]
        },
        "string-quoted": {
            "name": "string.quoted.double.nix",
            "begin": r"\"",
            "end": r"\"",
            "beginCaptures": {"0": {"name": "punctuation.definition.string.begin.nix"}},
            "endCaptures": {"0": {"name": "punctuation.definition.string.end.nix"}},
            "patterns": [
                {"name": "constant.character.escape.nix", "match": r"\\."},
                {"include": "#interpolation"},
            ],
        },
        "string-indented": {
            "name": "string.quoted.other.indented.nix",
            "begin": r"''",
            "end": r"''(?!['$\\])",
            "beginCaptures": {"0": {"name": "punctuation.definition.string.begin.nix"}},
            "endCaptures": {"0": {"name": "punctuation.definition.string.end.nix"}},
            "patterns": [
                {"name": "constant.character.escape.nix", "match": r"'''"},
                {"name": "constant.character.escape.nix", "match": r"''\$\{"},
                {"name": "constant.character.escape.nix", "match": r"''\\."},
                {"include": "#interpolation"},
            ],
        },
        "interpolation": {
            "name": "meta.interpolation.nix",
            "begin": r"\$\{",
            "end": r"\}",
            "beginCaptures": {"0": {"name": "punctuation.section.interpolation.begin.nix"}},
            "endCaptures": {"0": {"name": "punctuation.section.interpolation.end.nix"}},
            "patterns": [{"include": "#expression"}],
        },
        # Balanced-pair rules keep interpolation and folding correct.
        "block-braces": {
            "begin": r"\{",
            "end": r"\}",
            "beginCaptures": {"0": {"name": "punctuation.section.braces.begin.nix"}},
            "endCaptures": {"0": {"name": "punctuation.section.braces.end.nix"}},
            "patterns": [{"include": "#expression"}],
        },
        "block-brackets": {
            "begin": r"\[",
            "end": r"\]",
            "beginCaptures": {"0": {"name": "punctuation.section.brackets.begin.nix"}},
            "endCaptures": {"0": {"name": "punctuation.section.brackets.end.nix"}},
            "patterns": [{"include": "#expression"}],
        },
        "block-parens": {
            "begin": r"\(",
            "end": r"\)",
            "beginCaptures": {"0": {"name": "punctuation.section.parens.begin.nix"}},
            "endCaptures": {"0": {"name": "punctuation.section.parens.end.nix"}},
            "patterns": [{"include": "#expression"}],
        },
        "keywords": {
            "patterns": [
                {"name": "keyword.control.nix",
                 "match": GL + r"(if|then|else|assert|with|let|in)" + GR},
                {"name": "keyword.other.nix",
                 "match": GL + r"(rec|inherit)" + GR},
            ]
        },
        "constants": {
            "name": "constant.language.nix",
            "match": GL + r"(true|false|null)" + GR,
        },
        "uri": {
            "name": "string.unquoted.url.nix",
            "match": GL + r"[a-zA-Z][a-zA-Z0-9+.-]*:[a-zA-Z0-9%/?:@&=+$,_.!~*'-]+",
        },
        "search-path": {
            "name": "string.unquoted.spath.nix",
            "match": r"<[a-zA-Z0-9._+-]+(/[a-zA-Z0-9._+-]+)*>",
        },
        "path": {
            "name": "string.unquoted.path.nix",
            "match": r"(?<![\w'.+-])~?[a-zA-Z0-9._+-]*(/[a-zA-Z0-9._+-]+)+/?",
        },
        "attribute-def": {
            "name": "entity.other.attribute-name.nix",
            "match": (GL
                      + r"[a-zA-Z_][a-zA-Z0-9_'-]*"
                      + r"(\s*\.\s*([a-zA-Z_][a-zA-Z0-9_'-]*|\"[^\"]*\"|\$\{[^}]*\}))*"
                      + r"(?=\s*=(?!=))"),
        },
        "builtins": {
            "patterns": [
                {"name": "support.function.builtin.nix",
                 "match": GL + r"builtins\s*\.\s*[a-zA-Z_][a-zA-Z0-9_']*"},
                {"name": "support.function.builtin.nix",
                 "match": (GL
                           + r"(abort|baseNameOf|builtins|derivation|dirOf|fetchGit"
                           + r"|fetchMercurial|fetchTarball|fetchTree|fromTOML|import"
                           + r"|isNull|map|placeholder|removeAttrs|scopedImport|throw"
                           + r"|toString)" + GR)},
            ]
        },
        "number": {
            "patterns": [
                {"name": "constant.numeric.float.nix",
                 "match": r"(?<![\w.])(\d+\.\d*|\.\d+)([eE][+-]?\d+)?(?![\w.])"},
                {"name": "constant.numeric.integer.nix",
                 "match": r"(?<![\w.])\d+(?![\w.])"},
            ]
        },
        "function-param": {
            "patterns": [
                {"name": "variable.parameter.function.nix",
                 "match": GL + r"[a-zA-Z_][a-zA-Z0-9_'-]*(?=\s*[,?])"},
                {"name": "variable.parameter.function.nix",
                 "match": GL + r"[a-zA-Z_][a-zA-Z0-9_'-]*"
                          + r"(?=\s*:(?![a-zA-Z0-9%/?:@&=+$,_.!~*'-]))"},
            ]
        },
        "operators": {
            "patterns": [
                {"name": "keyword.operator.word.nix", "match": GL + r"or" + GR},
                {"name": "keyword.operator.nix",
                 "match": r"->|\+\+|//|==|!=|<=|>=|&&|\|\||\.\.\.|[-!+*<>@?/]"},
                {"name": "keyword.operator.assignment.nix", "match": r"="},
            ]
        },
        "punctuation": {
            "patterns": [
                {"name": "punctuation.terminator.statement.nix", "match": r";"},
                {"name": "punctuation.separator.comma.nix", "match": r","},
                {"name": "punctuation.separator.colon.nix", "match": r":"},
            ]
        },
    },
}

# ------------------------------------------------------------ preferences ---
comments_pref = {
    "name": "Comments",
    "scope": "source.nix",
    "settings": {
        "shellVariables": [
            {"name": "TM_COMMENT_START", "value": "# "},
            {"name": "TM_COMMENT_START_2", "value": "/*"},
            {"name": "TM_COMMENT_END_2", "value": "*/"},
        ]
    },
    "uuid": UUID_COMMENTS,
}

pairs_pref = {
    "name": "Typing Pairs",
    "scope": "source.nix",
    "settings": {
        "smartTypingPairs": [['"', '"'], ["{", "}"], ["[", "]"], ["(", ")"]],
        "highlightPairs": [["{", "}"], ["[", "]"], ["(", ")"]],
    },
    "uuid": UUID_PAIRS,
}

info = {
    "name": "Nix",
    "uuid": UUID_BUNDLE,
    "description": ("Support for the Nix expression language (.nix), as used by "
                    "NixOS, nix-darwin, Home Manager and the Nix package manager."),
    "contactName": "Sanja",
    "contactEmailRot13": "n@obhtnxbi.pbz",
}

README = """\
# Nix.tmbundle

[TextMate 2](https://macromates.com) support for the
[Nix expression language](https://nixos.org/manual/nix/stable/language/) —
the `.nix` files used by NixOS, nix-darwin, Home Manager and the Nix package
manager.

## Features

* Grammar (`source.nix`): line/block comments, double-quoted and `''`-indented
  strings with `${...}` interpolation (including the `''${`, `'''` and `''\\`
  escapes), paths, home paths, `<search-paths>` and unquoted URLs, keywords
  (`let`, `in`, `with`, `if`/`then`/`else`, `assert`, `rec`, `inherit`, `or`),
  the global builtins and `builtins.*`, attribute-path definitions
  (`services.nginx.enable = ...`), function parameters, integers and floats,
  and all operators.
* `⌘/` comment toggling (`#` and `/* ... */`).
* Smart typing pairs and brace-match highlighting.

## Installation

Either double-click `Nix.tmbundle`, or clone straight into TextMate's bundle
directory:

    mkdir -p ~/Library/Application\\ Support/TextMate/Bundles
    cd ~/Library/Application\\ Support/TextMate/Bundles
    git clone https://github.com/bougakov/nix.tmbundle.git

TextMate picks the bundle up automatically; `.nix` files are then highlighted
out of the box.

## Contributing

Bug reports and pull requests are welcome via
[GitHub](https://github.com/bougakov/nix.tmbundle). Please include a minimal
`.nix` snippet that demonstrates any highlighting issue.

## License

If not otherwise specified (see below), files in this repository fall under
the following license:

    Permission to copy, use, modify, sell and distribute this
    software is granted. This software is provided "as is" without
    express or implied warranty, and with no claim as to its
    suitability for any purpose.

An exception is made for files in readable text which contain their own
license information, or files where an accompanying file exists (in the same
directory) with a "-license" suffix added to the base-name of the original
file, and an extension of txt, html, or similar.
"""

# ------------------------------------------------------------- test file ----
TEST_NIX = """\
# NixOS configuration — syntax smoke test for the Nix bundle
/* block comment
   spanning two lines */
{ config, pkgs, lib ? import <nixpkgs/lib>, ... } @ args:

let
  host = "web-01";
  greeting = "hello \\"${config.networking.hostName}\\"\\n";
  motd = ''
    Welcome to ${host}!
    Literal dollar-brace: ''${keep} and doubled quote: '''
    Escaped newline: ''\\n
  '';
  root = /etc/nixos;
  module = ./modules/web.nix;
  homeDir = ~/projects/site;
  cache = https://cache.nixos.org;
  fraction = 6/3;        # a path, not division
  quotient = 6 / 3;      # division
  scale = 1.5e3;
  answer = 42;
in
rec {
  imports = [ module ];
  services.nginx.enable = true;
  services.nginx.virtualHosts."example.org".root = root;
  environment.systemPackages = with pkgs; [ curl git ];
  networking.hostName = host;
  boot.kernelParams = [ "quiet" ] ++ [ "splash" ];
  status = if config.services.nginx.enable or false then "on" else null;
  src = builtins.fetchTarball {
    url = "https://example.org/src.tar.gz";
    sha256 = lib.fakeSha256;
  };
  doubled = assert answer != 0; map (v: v * 2) [ 1 2 3 answer ];
  inherit (pkgs) stdenv;
}
"""

# ------------------------------------------------------------------ build ---
def dump(path: pathlib.Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fp:
        plistlib.dump(value, fp, sort_keys=False)
    with open(path, "rb") as fp:          # validate round-trip
        plistlib.load(fp)
    print(f"OK  {path.relative_to(ROOT)}")


def check_regexes(node, ctx="grammar"):
    """Sanity-compile every regex with Python re (approximation of Oniguruma)."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("match", "begin", "end", "foldingStartMarker",
                     "foldingStopMarker") and isinstance(v, str):
                try:
                    re.compile(v)
                except re.error as e:
                    print(f"REGEX FAIL [{ctx}] {v!r}: {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                check_regexes(v, ctx)
    elif isinstance(node, list):
        for item in node:
            check_regexes(item, ctx)


if __name__ == "__main__":
    check_regexes(grammar)
    dump(BUNDLE / "info.plist", info)
    dump(BUNDLE / "Syntaxes" / "Nix.tmLanguage", grammar)
    dump(BUNDLE / "Preferences" / "Comments.tmPreferences", comments_pref)
    dump(BUNDLE / "Preferences" / "Typing Pairs.tmPreferences", pairs_pref)
    (BUNDLE / "README.md").write_text(README, encoding="utf-8")
    print("OK  Nix.tmbundle/README.md")
    (ROOT / "test.nix").write_text(TEST_NIX, encoding="utf-8")
    print("OK  test.nix")
    shutil.make_archive(str(ROOT / "Nix.tmbundle"), "zip",
                        root_dir=ROOT, base_dir="Nix.tmbundle")
    print("OK  Nix.tmbundle.zip")
