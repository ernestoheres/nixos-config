{ config, pkgs, ... }:

{
  environment.systemPackages = [ pkgs.ryzenadj ];

  # We replace the timer with a continuous service
  systemd.services.ryzen-throttle-fix = {
    description = "Continuous aggressive override for EC throttling";
    wantedBy = [ "multi-user.target" ]; # Start automatically on boot
    serviceConfig = {
      Type = "simple";
      Restart = "always";
      # Run a loop that reapplies settings every 1.5 seconds
      ExecStart = pkgs.writeShellScript "ryzen-loop" ''
        while true; do
          ${pkgs.ryzenadj}/bin/ryzenadj --stapm-limit=54000 --fast-limit=65000 --slow-limit=60000 --tctl-temp=95 --vrm-current=100000
          sleep 0.5
        done
      '';
    };
  };
}

