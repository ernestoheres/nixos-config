# Include untracked experiment files without staging the user's work. Exclude
# generated evidence and the convenience checkout from the flake source snapshot.
builtins.path {
  path = ../..;
  name = "turing-experiment-worktree";
  filter = path: type:
    let
      name = baseNameOf path;
      parent = baseNameOf (dirOf path);
    in !(builtins.elem name [ ".git" "__pycache__" ])
      && !(parent == "turing-unlock" && builtins.elem name [ "results" "source" ]);
}
