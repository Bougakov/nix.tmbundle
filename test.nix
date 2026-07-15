# NixOS configuration — syntax smoke test for the Nix bundle
/* block comment
   spanning two lines */
{ config, pkgs, lib ? import <nixpkgs/lib>, ... } @ args:

let
  host = "web-01";
  greeting = "hello \"${config.networking.hostName}\"\n";
  motd = ''
    Welcome to ${host}!
    Literal dollar-brace: ''${keep} and doubled quote: '''
    Escaped newline: ''\n
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
