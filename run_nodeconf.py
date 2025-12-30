#!/usr/bin/env python3

from cuemsutils.daemon import run_daemon
from cuemsutils.log import Logger
from .CuemsNodeConf import CuemsNodeConf



def main():
    # Create and run engine
    nodeconf = CuemsNodeConf()
    Logger.debug('CuemsNodeConf instance created, going start to daemon')
    run_daemon(nodeconf, 'nodeconf')

if __name__ == '__main__':
    main()