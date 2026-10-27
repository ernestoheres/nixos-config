# Imported ONLY by the separate default-turing-experiment flake output.
{ ... }:
{
  specialisation.turing-experiment.configuration = import ./experiment.nix;
}
