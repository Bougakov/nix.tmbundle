// Tokenize test.nix with vscode-textmate + oniguruma and assert expected scopes.
const fs = require("fs");
const vsctm = require("/tmp/tmtest/node_modules/vscode-textmate");
const onig = require("/tmp/tmtest/node_modules/vscode-oniguruma");

const OUT = "/sessions/vigilant-fervent-gates/mnt/outputs";
const GRAMMAR = OUT + "/Nix.tmbundle/Syntaxes/Nix.tmLanguage";
const SAMPLE = OUT + "/test.nix";

(async () => {
  const wasm = fs.readFileSync(
    "/tmp/tmtest/node_modules/vscode-oniguruma/release/onig.wasm").buffer;
  await onig.loadWASM(wasm);
  const registry = new vsctm.Registry({
    onigLib: Promise.resolve({
      createOnigScanner: (p) => new onig.OnigScanner(p),
      createOnigString: (s) => new onig.OnigString(s),
    }),
    loadGrammar: async (scope) =>
      scope === "source.nix"
        ? vsctm.parseRawGrammar(fs.readFileSync(GRAMMAR, "utf8"), GRAMMAR)
        : null,
  });
  const grammar = await registry.loadGrammar("source.nix");
  if (!grammar) { console.error("grammar failed to load"); process.exit(2); }

  const lines = fs.readFileSync(SAMPLE, "utf8").split("\n");
  let ruleStack = vsctm.INITIAL;
  const dumpLines = [];
  for (const line of lines) {
    const r = grammar.tokenizeLine(line, ruleStack);
    for (const t of r.tokens) {
      const text = line.slice(t.startIndex, t.endIndex);
      if (text.trim().length)
        dumpLines.push(JSON.stringify(text) + "  ::  " + t.scopes.join(" "));
    }
    ruleStack = r.ruleStack;
  }
  const dump = dumpLines.join("\n");
  fs.writeFileSync(OUT + "/token_dump.txt", dump);

  let fail = 0;
  const bad = (msg) => { console.error("FAIL: " + msg); fail = 1; };

  // 1) every scope family must appear
  for (const s of [
    "comment.line.number-sign.nix", "comment.block.nix",
    "string.quoted.double.nix", "string.quoted.other.indented.nix",
    "meta.interpolation.nix", "constant.character.escape.nix",
    "string.unquoted.path.nix", "string.unquoted.spath.nix",
    "string.unquoted.url.nix",
    "keyword.control.nix", "keyword.other.nix", "keyword.operator.word.nix",
    "constant.language.nix", "support.function.builtin.nix",
    "entity.other.attribute-name.nix", "variable.parameter.function.nix",
    "constant.numeric.float.nix", "constant.numeric.integer.nix",
    "keyword.operator.nix", "keyword.operator.assignment.nix",
  ]) if (!dump.includes(s)) bad("scope never produced: " + s);

  // 2) targeted token → scope expectations
  const expect = [
    ["let", "keyword.control.nix"],
    ["rec", "keyword.other.nix"],
    ["true", "constant.language.nix"],
    ["null", "constant.language.nix"],
    ["./modules/web.nix", "string.unquoted.path.nix"],
    ["~/projects/site", "string.unquoted.path.nix"],
    ["/etc/nixos", "string.unquoted.path.nix"],
    ["6/3", "string.unquoted.path.nix"],
    ["<nixpkgs/lib>", "string.unquoted.spath.nix"],
    ["https://cache.nixos.org", "string.unquoted.url.nix"],
    ["services.nginx.enable", "entity.other.attribute-name.nix"],
    ["services.nginx.virtualHosts.\"example.org\".root", "entity.other.attribute-name.nix"],
    ["builtins.fetchTarball", "support.function.builtin.nix"],
    ["map", "support.function.builtin.nix"],
    ["import", "support.function.builtin.nix"],
    ["1.5e3", "constant.numeric.float.nix"],
    ["42", "constant.numeric.integer.nix"],
    ["or", "keyword.operator.word.nix"],
    ["++", "keyword.operator.nix"],
    ["config", "variable.parameter.function.nix"],   // { config, pkgs, ... }
    ["'''", "constant.character.escape.nix"],
    ["''${", "constant.character.escape.nix"],
  ];
  for (const [text, scope] of expect) {
    const hit = dumpLines.find(
      (l) => l.startsWith(JSON.stringify(text) + "  ") && l.includes(scope));
    if (!hit) bad(`token ${JSON.stringify(text)} lacks scope ${scope}`);
  }

  // 3) negative checks
  const q = dumpLines.find((l) => l.startsWith('"quotient"'));
  if (!q || !q.includes("entity.other.attribute-name")) bad("quotient not an attribute");
  const urlInString = dumpLines.find(
    (l) => l.includes("example.org/src.tar.gz") && l.includes("string.unquoted.url"));
  if (urlInString) bad("URL inside a quoted string wrongly scoped as unquoted url");

  console.log(fail ? "RESULT: FAILURES (see above)" : "RESULT: ALL CHECKS PASSED");
  console.log("tokens dumped: " + dumpLines.length);
  process.exit(fail);
})().catch((e) => { console.error(e); process.exit(2); });
