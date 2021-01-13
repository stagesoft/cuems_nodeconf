

import logging
import time


from CuemsNodeConf import CuemsNodeConf
logging.basicConfig(level=logging.DEBUG,
                    format='%(name)s: %(message)s',
                    )





try:
    nodeconf = CuemsNodeConf()
    input("press enter to shutdown \n")
finally:
    nodeconf.shutdown()
