{ inputs
, ...
}:
let in {
  programs.doom-emacs = {
    enable = true;
    doomDir = "./doom.d";
  };
}
