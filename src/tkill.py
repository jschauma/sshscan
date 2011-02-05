#! /usr/bin/env python
#
# Copyright (c) 2007,2011 Yahoo! Inc.
# All rights reserved.
#
# Originally written by Jan Schaumann <jschauma@yahoo-inc.com> in July 2007.
#
# Redistribution and use of this software in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# * Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.
#
# * Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.
#
# * Neither the name of Yahoo! Inc. nor the names of its
#   contributors may be used to endorse or promote products
#   derived from this software without specific prior
#   written permission of Yahoo! Inc.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#
# This program kills a given process or process group if it has been running
# for longer than a specified time.
#
# See http://mail-index.netbsd.org/tech-userlevel/2007/07/26/0003.html for
# a patch to NetBSD's pkill(1) sources.

import getopt
import os
import re
import string
import sys
import time

###
### Globals
###

EXIT_ERROR = 1
EXIT_SUCCESS = 0

PS_CMD = "ps -awwx -o lstart,pid,ppid,command"

SIGNALS = [ "HUP",  "INT",  "QUIT", "ILL",  "TRAP", "ABRT", "EMT",  "FPE",
            "KILL", "BUS",  "SEGV", "SYS",  "PIPE", "ALRM", "TERM", "URG",
            "STOP", "TSTP", "CONT", "CHLD", "TTIN", "TTOU", "IO",   "XCPU",
            "XFSZ", "VTALRM","PROF","WINCH","INFO", "USR1", "USR2", "PWR" ]

CMD = ""
LOOSE_MATCH = False
PARENT = False
PIDS = []
SIG = "TERM"
TIMEOUT = 300

###
### Subroutines
###

def usage():
    """print short usage"""

    print 'Usage: %s [-P] [-h] [-l] [-t timeout] [-s signal] (pid [...] | -c cmd)'  \
                % sys.argv[0]
    print '\t-C cmd      kill processes containing the given command string'
    print '\t-P          kill all processes whose parent is pid'
    print '\t-c cmd      kill processes matching given command exactly'
    print '\t-h          print this help and exit'
    print '\t-l          print list of valid signals'
    print '\t-t timeout  specify timeout in seconds (default: 300)'
    print '\t-s signal   kill with given signal (default: TERM)'



def isValidSignal(sig):
    """validate the given signal by checking if it is a valid numerical signal
       or as a string in the array of signals we know"""

    try:
        s = string.atoi(sig)
        if (s < 1) or (s > 32):
            raise ValueError("illegal numerical signal %d" % sig)
    except:
        for s in SIGNALS:
            if sig == s:
                return sig
        raise ValueError("illegal numerical signal %s" % sig)

    return sig



def parseOpts():
    """parse command-line options and act on them"""

    global CMD, LOOSE_MATCH, PARENT, SIG, TIMEOUT

    try:
        opts, args = getopt.getopt(sys.argv[1:], "C:Pc:hlt:s:")
    except getopt.GetoptError:
        usage()
        sys.exit(EXIT_ERROR)
        # NOTREACHED

    for o, a in opts:
        if o in ("-C"):
            CMD = a
            LOOSE_MATCH = True
        if o in ("-P"):
            PARENT = True
        if o in ("-c"):
            CMD = a
        if o in ("-h"):
            usage()
            sys.exit(EXIT_SUCCESS)
            # NOTREACHED
        if o in ("-l"):
            for s in SIGNALS:
                sys.stdout.write("%s " % s)
            sys.stdout.write("\n")
            sys.exit(EXIT_SUCCESS)
            # NOTREACHED
        if o in ("-t"):
            try:
                TIMEOUT = string.atoi(a)
            except:
                sys.stderr.write('%s: -t: not a number: "%s"\n' % (sys.argv[0], a))
                sys.exit(EXIT_ERROR)
                # NOTREACHED
        if o in ("-s"):
            try:
                SIG = isValidSignal(a)
            except ValueError:
                sys.stderr.write('%s: -s: bad signal `%s\'\n' % (sys.argv[0], a))
                sys.exit(EXIT_ERROR)
                # NOTREACHED

    if args:
        if CMD:
            usage()
            sys.exit(EXIT_ERROR)
            # NOTREACHED
        else:
            try:
                for p in args:
                    PIDS.append(string.atoi(p))
            except ValueError:
                sys.stderr.write('%s: bad pid `%s\'\n' % (sys.argv[0], p))
                sys.exit(EXIT_ERROR)
                # NOTREACHED
    else:
        if not CMD:
            usage()
            sys.exit(EXIT_ERROR)
            # NOTREACHED



def isStalePid(start):
    """return true if the given processes running time has been longer than
       the limit"""

    global TIMEOUT

    now = time.time()
    if start < (now - TIMEOUT):
        return True

    return False



def killAllStalePids():
    """open a pipe to the PS command and parse the output"""

    global CMD, LOOSE_MATCH, PARENT, PIDS, PS_CMD

    ps = os.popen(PS_CMD)
    while 1:
        line = ps.readline()
        if not line:
            break
        p = re.compile("^(\S+ \S+ +\d+ [0-9:]+ \d+)\s+(\d+)\s+(\d+)\s+(.*)$")
        m = p.match(line)

        if not m:
            continue

        (start, pid, ppid, comm) = m.groups()

        t = time.strptime(start)
        start = time.mktime(t)

        pid = string.atoi(pid)
        ppid = string.atoi(ppid)

        if ( ((CMD == comm.strip()) or \
             (LOOSE_MATCH and (comm.find(CMD) >= 0))) \
             and isStalePid(start) ):
            killPid(pid)

        for p in PIDS:
            if not isStalePid(start):
                continue
            if PARENT:
                if p == ppid:
                    killPid(p)
            else:
                if p == pid:
                    killPid(p)



def killPid(p):
    """kill a process"""

    s = SIGNALS.index(SIG) + 1
    try:
        os.kill(p,s)
    except Exception, (errno, strerror):
        sys.stderr.write('%s: unable to kill PID %d: %s\n' % \
                            (sys.argv[0], p, strerror))

###
### Main
###

if __name__ == "__main__":
    parseOpts()
    killAllStalePids()
