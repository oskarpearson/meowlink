from __future__ import print_function
# From https://github.com/bewest/decoding-carelink/blob/314406d5d6025321dbe1a7d48a202b608df41c30/decocare/fuser.py
# This still has race conditions, but is better than nothing for the moment,
# as not all other apps use lock files

import os
import sys
from subprocess import Popen, PIPE

def in_use (device):
  if 'windows' in sys.platform:
    # TODO: use Handle
    # http://stackoverflow.com/questions/18059798/windows-batch-equivalent-of-fuser-k-folder
    # https://technet.microsoft.com/en-us/sysinternals/bb896655
    return False
  pipe = Popen(['fuser', device], stdout=PIPE, stderr=PIPE)
  stdout, stderr = pipe.communicate( )

  # Seriously hacky: don't raise an error if it's our own process ID
  stdout = stdout.strip()
  return stdout not in ['', str(os.getpid())]

if __name__ == '__main__':
  from scan import scan
  candidate = (sys.argv[1:2] or [scan( )]).pop( )
  print(in_use(candidate))
