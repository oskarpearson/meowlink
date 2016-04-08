#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

from mmeowlink.cli import messages

if __name__ == '__main__':
    app = messages.SendBolusApp()
    app.run(None)
