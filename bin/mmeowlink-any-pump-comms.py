#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

"""
Checks to see if there are any pump comms going on. If there are: exits with an error status
"""

import sys

from mmeowlink.cli.any_pump_comms_app import AnyPumpCommsApp

if __name__ == '__main__':
  app = AnyPumpCommsApp()

  app.run(None)

  # app.run doesn't return the call status, so we need to interrogate the object:
  if app.app_result == 0:
    print("No comms detected")
  else:
    print("Comms with pump detected")

  sys.exit(app.app_result)
