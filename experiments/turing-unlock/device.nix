# Discovered from lspci -Dnn and sysfs on 2026-10-25; not a generic GPU preset.
{
  nvidia = {
    pci = "0000:01:00.0";
    vendor = "10de";
    device = "1f15";
  };
  igpu = {
    pci = "0000:06:00.0";
    vendor = "1002";
    device = "1636";
    driver = "amdgpu";
  };
}
