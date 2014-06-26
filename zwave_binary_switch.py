#!/usr/bin/env python
# tempo.py
# Copyright (C) ContinuumBridge Limited, 2014 - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Peter Claydon
#
ModuleName = "zwave_binary_switch"

import sys
import time
import os
import logging
from cbcommslib import CbAdaptor
from cbconfig import *
from twisted.internet import threads
from twisted.internet import reactor

class Adaptor(CbAdaptor):
    def __init__(self, argv):
        logging.basicConfig(filename=CB_LOGFILE,level=CB_LOGGING_LEVEL,format='%(asctime)s %(message)s')
        self.status = "ok"
        self.state = "stopped"
        initMsg = {"id": self.id,
                   "type": "app",
                   "status": "req-config"} 
        self.managerFactory = CbClientFactory(self.processManager, initMsg)
        reactor.connectUNIX(managerSocket, self.managerFactory, timeout=10)

        reactor.callLater(TIME_TO_MONITOR_STATUS, self.sendStatus)
        # super's __init__ must be called:
        super(Adaptor, self).__init__(argv)
        #CbAdaptor.__init__(self, argv)
 
    def setState(self, action):
        if self.state == "stopped":
            if action == "starting":
                self.state = "starting"
        elif self.state == "starting":
            if action == "inUse":
                self.state = "activate"
        if self.state == "activate":
            reactor.callLater(0, self.poll)
            self.state = "running"
        # error is only ever set from the running state, so set back to running if error is cleared
        if action == "error":
            self.state == "error"
        elif action == "clear_error":
            self.state = "running"
        logging.debug("%s %s state = %s", ModuleName, self.id, self.state)
        msg = {"id": self.id,
               "status": "state",
               "state": self.state}
        self.sendManagerMessage(msg)

    def reportState(self, state):
        logging.debug("%s %s Switch state = %s", ModuleName, self.id, state)
        msg = {"id": self.id,
               "timeStamp": time.time(),
               "content": "switch_state",
               "data": state}
        for a in self.apps:
            self.sendMessage(msg, a)

    def sendParameter(self, parameter, data, timeStamp):
        msg = {"id": self.id,
               "content": parameter,
               "data": data,
               "timeStamp": timeStamp}
        for a in self.apps[parameter]:
            reactor.callFromThread(self.sendMessage, msg, a)

    def onStop(self):
        # Mainly caters for situation where adaptor is told to stop while it is starting
        pass

    def checkAllProcessed(self, appID):
        self.processedApps.append(appID)
        found = True
        for a in self.appInstances:
            if a not in self.processedApps:
                found = False
        if found:
            self.setState("inUse")

    def onOff(self, s):
        if s == "on":
            return "255"
        else:
            return "0"

    def switch(self, onOrOff):
        cmd = ("id": self.id,
               "address": self.address,
               "instance": "0",
               "commandClass": "50",
               "value": self.onOff(onOrOff)
              }
        self.sendZwaveMessage(cmd):

    def onAppInit(self, message):
        logging.debug("%s %s %s onAppInit, req = %s", ModuleName, self.id, self.friendly_name, message)
        resp = {"name": self.name,
                "id": self.id,
                "status": "ok",
                "functions": [{"parameter": "switch",
                               "type": "240V",
                               "purpose": "heater"}],
                "content": "functions"}
        self.sendMessage(resp, message["id"])

    def onAppCommand(self, message):
        # If at first it doesn't succeed, try again.
        if not message["data"]:
            logging.warning("%s %s %s app message without data: %s", ModuleName, self.id, self.friendly_name, message)
        elif message["data"] != "on" or message["data"] != off:
            logging.warning("%s %s %s app switch state must be on or off: %s", ModuleName, self.id, self.friendly_name, message)
        else:
            self.switch(message["data"])

    def onConfigureMessage(self, config):
        """Config is based on what apps are to be connected.
            May be called again if there is a new configuration, which
            could be because a new app has been added.
        """
        self.setState("starting")

if __name__ == '__main__':
    adaptor = Adaptor(sys.argv)
