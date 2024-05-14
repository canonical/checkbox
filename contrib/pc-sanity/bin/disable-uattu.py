#!/usr/bin/python3
import softwareproperties
from softwareproperties import SoftwareProperties
s = SoftwareProperties.SoftwareProperties()

s.set_update_automation_level(softwareproperties.UPDATE_MANUAL)

print("OK")
