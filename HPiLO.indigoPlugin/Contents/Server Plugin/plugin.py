#! /usr/bin/env python2.6
# -*- coding: utf-8 -*-

"""
Author: GlennNZ

"""

import datetime
import time as t
import xml.etree.ElementTree as Etree
import urllib2
import os
import ssl
import shutil
import logging
import socket
import sys
import hpilo
import simplejson
import re
import flatdict
import iterateXML
from datetime import timedelta

try:
    import indigo
except:
    pass


class Plugin(indigo.PluginBase):
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        try:
            self.logLevel = int(self.pluginPrefs[u"showDebugLevel"])
        except:
            self.logLevel = logging.INFO

        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(u"logLevel = " + str(self.logLevel))

        self.prefsUpdated = False
        self.logger.info(u"")
        self.logger.info(u"{0:=^130}".format(" Initializing New Plugin Session "))
        self.logger.info(u"{0:<30} {1}".format("Plugin name:", pluginDisplayName))
        self.logger.info(u"{0:<30} {1}".format("Plugin version:", pluginVersion))
        self.logger.info(u"{0:<30} {1}".format("Plugin ID:", pluginId))
        self.logger.info(u"{0:<30} {1}".format("Indigo version:", indigo.server.version))
        self.logger.info(u"{0:<30} {1}".format("Python version:", sys.version.replace('\n', '')))
        self.logger.info(u"{0:<30} {1}".format("Python Directory:", sys.prefix.replace('\n', '')))

        # Change to logging
        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s',
                                 datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        self.connected = False
        self.deviceUpdate = False
        self.devicetobeUpdated =''

        self.labelsdueupdate = True
        self.debug1 = self.pluginPrefs.get('debug1', False)
        self.debug2 = self.pluginPrefs.get('debug2', False)
        self.debug3 = self.pluginPrefs.get('debug3', False)
        self.debug4 = self.pluginPrefs.get('debug4',False)
        self.debug5 = self.pluginPrefs.get('debug5', False)

        # main device to be updated as needed
        self.finalDict = {}
        self.triggers = {}

        self.logger.info(u"{0:=^130}".format(" End Initializing New Plugin  "))

    def __del__(self):

        self.debugLog(u"__del__ method called.")
        indigo.PluginBase.__del__(self)

    def closedPrefsConfigUi(self, valuesDict, userCancelled):

        self.debugLog(u"closedPrefsConfigUi() method called.")

        if userCancelled:
            self.debugLog(u"User prefs dialog cancelled.")

        if not userCancelled:
            self.logLevel = int(valuesDict.get("showDebugLevel", '5'))

            self.debugLog(u"User prefs saved.")
            self.debug1 = valuesDict.get('debug1', False)
            self.debug2 = valuesDict.get('debug2', False)
            self.debug3 = valuesDict.get('debug3', False)
            self.debug4 = valuesDict.get('debug4', False)
            self.debug5 = valuesDict.get('debug5', False)
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(u"logLevel = " + str(self.logLevel))
            self.logger.debug(u"User prefs saved.")
            self.logger.debug(u"Debugging on (Level: {0})".format(self.logLevel))

        return True

    # Start 'em up.

    # Shut 'em down.
    def deviceStopComm(self, dev):

        self.debugLog(u"deviceStopComm() method called.")
        dev.updateStateOnServer('deviceIsOnline', value=False)
        dev.updateStateOnServer("onOffState", value=False)
        dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)


    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

    def checkForUpdates(self):
        if self.updater.checkForUpdate() == False:
            indigo.server.log(u"No Updates are Available")

    def updatePlugin(self):
        self.updater.update()

    def get_the_data_subType(self, dev, type):
        try:
            ipaddress = dev.pluginProps.get('ipaddress', "")
            username = dev.pluginProps.get('username', "")
            password = dev.pluginProps.get('password', "")
            self.logger.debug(u"Connecting to IP " + unicode(ipaddress) + " with username" + unicode(
                username) + " and password:" + unicode(password))
            ilo = hpilo.Ilo(ipaddress, login=username, password=password, timeout=10)

            update_time = t.strftime('%c')
            dev.updateStateOnServer('deviceLastUpdated', value=str(update_time))
            dev.updateStateOnServer('deviceIsOnline', value=True )

            info = {}
            if type=="health":
                health = ilo.get_embedded_health()
                self.process_data(dev, health, type)
            elif type =="fw_version":
                fw_version = ilo.get_fw_version()
                self.process_data(dev, fw_version, type)
            elif type =="poweron":
                timeon = ilo.get_server_power_on_time()
                self.logger.debug("Timeon:"+unicode(timeon))
                self.process_data(dev, timeon, type)
            elif type == "hostdata":
                host_data = ilo.get_host_data()
                self.process_data(dev, host_data, type)
            elif type =="power":
                power_readings = ilo.get_power_readings()
                self.process_data(dev, power_readings, "power")
            elif type =="power_status":
                power_status = ilo.get_host_power_status()
                self.process_data(dev, power_status,"power_status")

            return info


        except hpilo.IloCommunicationError:
            self.logger.exception("Error communicating with HP iLO")
            dev.updateStateOnServer('deviceIsOnline', value=False)
            return None
        except hpilo.IloLoginFailed:
            self.logger.info("Login to iLO failed - check Password Username security settings")
            dev.updateStateOnServer('deviceIsOnline', value=False)
            return None
        except hpilo.IloFeatureNotSupported:
            self.logger.debug("Some Features not supported. Ignored.")
            pass
        except Exception:
            self.logger.exception("Exception Found")
            dev.updateStateOnServer('deviceIsOnline', value=False)
            return None

    def process_data(self, dev, data, type):
        self.logger.debug("ProcesData Called for Type:"+unicode(type))
        try:
            if type == "hostdata":
                #for item in data:
                    #self.logger.info(unicode(item))
                stateList = [
                    {'key': 'Host_BIOS_Date', 'value': data[0]['Date']},
                    {'key': 'Host_UUID', 'value': data[1]['UUID']},
                    {'key': 'Host_ProductName', 'value': data[1]['Product Name']},
                    {'key': 'Host_SerialNumber', 'value': data[1]['Serial Number']}
                ]
                dev.updateStatesOnServer(stateList)
            elif type=="health":
                stateList = []
                try:
                    for item in data['temperature']:
                        #self.logger.info(unicode(item))
                        try:
                            nameofstate =""
                            nameofstate = ("Temp_"+data['temperature'][item]['label']).replace(" ","_").replace("-","_")
                            dataofstate = data['temperature'][item]['currentreading'][0]
                            stateListappend =    {'key': nameofstate, 'value': dataofstate}
                            if nameofstate !="" and nameofstate in dev.states:
                                stateList.append(stateListappend)
                            nameofstate = ("Temp_"+data['temperature'][item]['label']+"_Status").replace(" ","_").replace("-","_")
                            dataofstate = data['temperature'][item]['status']
                            stateListappend = {'key': nameofstate, 'value': dataofstate}
                            if nameofstate !="" and nameofstate in dev.states:
                                stateList.append(stateListappend)
                        except:
                            self.logger.debug("Exception in Temp Skipped")
                            nameofstate =""
                            pass


                except Exception as e:
                    self.logger.debug("Exception in Data Temperature:"+unicode(e.Message))

                try:
                    for item in data['fans']:
                        #self.logger.info(unicode(item))
                        try:
                            nameofstate = ""
                            nameofstate = (data['fans'][item]['label']+"_Speed").replace(" ","_")
                            dataofstate = data['fans'][item]['speed'][0]
                            stateListappend =    {'key': nameofstate, 'value': dataofstate}
                            if nameofstate !="" and nameofstate in dev.states:
                                stateList.append(stateListappend)
                            elif nameofstate != "" and nameofstate not in dev.states:
                                self.logger.debug(unicode(
                                    nameofstate) + " NOT found in device states.  Please let Developer know and can add support")

                            nameofstate = (data['fans'][item]['label']+"_Status").replace(" ","_")
                            dataofstate = data['fans'][item]['speed'][0]
                            stateListappend = {'key': nameofstate, 'value': dataofstate}
                            if nameofstate != "" and nameofstate in dev.states:
                                stateList.append(stateListappend)
                            elif nameofstate != "" and nameofstate not in dev.states:
                                self.logger.debug(unicode(
                                    nameofstate) + " NOT found in device states.  Please let Developer know and can add support")
                        except:
                            self.logger.debug("Exception in fans")
                            nameofstate =""

                except Exception as e:
                    self.logger.debug("Exception in Data Fans:"+unicode(e.Message))

                try:
                    for item in data['health_at_a_glance']:
                        # self.logger.info(unicode(item))
                        try:
                            nameofstate =""
                            nameofstate =  "Health_Summary_"+item+"_Status"
                            dataofstate = data['health_at_a_glance'][item]['status']
                            stateListappend = {'key': nameofstate, 'value': dataofstate}
                            if nameofstate != "" and nameofstate in dev.states:
                                stateList.append(stateListappend)
                            elif nameofstate!="" and nameofstate not in dev.states:
                                self.logger.debug(unicode(nameofstate)+" NOT found in device states.  Please let Developer know and can add support")
                        except:
                            self.logger.debug("Exception Health at glance")
                            nameofstate = ""

                except Exception as e:
                    self.logger.debug("Exception in Health at a Glance:" + unicode(e.Message))

                self.logger.debug(unicode(stateList))
                dev.updateStatesOnServer(stateList)

            elif type=="fw_version":
                stateList = []
                nameofstate = "Host_iLO_Firmware_Version"
                dataofstate = data['firmware_version']
                stateListappend = {'key': nameofstate, 'value': dataofstate}
                stateList.append(stateListappend)

                nameofstate = "Host_iLO_License_Version"
                dataofstate = data['license_type']
                stateListappend = {'key': nameofstate, 'value': dataofstate}
                stateList.append(stateListappend)
                self.logger.debug(unicode(stateList))
                dev.updateStatesOnServer(stateList)

            elif type=="poweron":
                dev.updateStateOnServer("Host_PowerOnTime_Minutes", data)
                dev.updateStateOnServer("Host_PowerOnTime_String", str(datetime.timedelta(minutes=data)))

            elif type =="power":
                #data = {'average_power_reading': (65, 'Watts'), 'maximum_power_reading': (101, 'Watts'), 'minimum_power_reading': (65, 'Watts'), 'present_power_reading': (67, 'Watts')}
                stateList = []
                nameofstate = "Power_Minimum"
                dataofstate = data['minimum_power_reading'][0]
                stateListappend = {'key': nameofstate, 'value': dataofstate}
                stateList.append(stateListappend)

                nameofstate = "Power_Maximum"
                dataofstate = data['maximum_power_reading'][0]
                stateListappend = {'key': nameofstate, 'value': dataofstate}
                stateList.append(stateListappend)

                nameofstate = "Power_Present"
                dataofstate = data['present_power_reading'][0]
                stateListappend = {'key': nameofstate, 'value': dataofstate}
                stateList.append(stateListappend)

                nameofstate = "Power_Average"
                dataofstate = data['average_power_reading'][0]
                stateListappend = {'key': nameofstate, 'value': dataofstate}
                stateList.append(stateListappend)
                self.logger.debug(unicode(stateList))
                dev.updateStatesOnServer(stateList)

            elif type=="power_status":
                if data=="ON" and dev.states["onOffState"]==False:
                    dev.updateStateOnServer("onOffState", value=True)
                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                    self.logger.debug("Power_status:" + unicode(data))
                elif data =="OFF" and dev.states["onOffState"]:
                    dev.updateStateOnServer("onOffState", value=False)
                    dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
                    self.logger.debug("Power_status OFF:" + unicode(data))
#commit
            return

        except:
            self.logger.exception("Caught Exception Process data")
            return


    # def getDeviceStateList(self, dev):
    #     state_list = indigo.PluginBase.getDeviceStateList(self, dev)
    #     if state_list is not None:
    #         # Add any dynamic states onto the device based on the node's characteristics.
    #         if dev.enabled:
    #             for key in sorted(self.finalDict.keys()):
    #                 value = self.finalDict[key]
    #                 try:
    #                     # Integers
    #                     _ = int(value)
    #                     state_list.append(
    #                         self.getDeviceStateDictForNumberType(unicode(key), unicode(key), unicode(key)))
    #                 except (TypeError, ValueError):
    #                     try:
    #                         # Floats
    #                         _ = float(value)
    #                         state_list.append(
    #                             self.getDeviceStateDictForNumberType(unicode(key), unicode(key), unicode(key)))
    #                     except (TypeError, ValueError):
    #                         try:
    #                             # Bools - we create a state for the original data (in string form) and for the boolean representation.
    #                             if value.lower() in (
    #                             'on', 'off', 'open', 'locked', 'up', 'armed', 'closed', 'unlocked', 'down', 'disarmed'):
    #                                 state_list.append(
    #                                     self.getDeviceStateDictForBoolOnOffType(unicode(key), unicode(key),
    #                                                                             unicode(key)))
    #                                 state_list.append(
    #                                     self.getDeviceStateDictForBoolOnOffType(unicode(u"{0}_bool".format(key)),
    #                                                                             unicode(u"{0}_bool".format(key)),
    #                                                                             unicode(u"{0}_bool".format(key))))
    #                             elif value.lower() in ('yes', 'no'):
    #                                 state_list.append(
    #                                     self.getDeviceStateDictForBoolYesNoType(unicode(key), unicode(key),
    #                                                                             unicode(key)))
    #                                 state_list.append(
    #                                     self.getDeviceStateDictForBoolYesNoType(unicode(u"{0}_bool".format(key)),
    #                                                                             unicode(u"{0}_bool".format(key)),
    #                                                                             unicode(u"{0}_bool".format(key))))
    #                             elif value.lower() in ('true', 'false'):
    #                                 state_list.append(
    #                                     self.getDeviceStateDictForBoolTrueFalseType(unicode(key), unicode(key),
    #                                                                                 unicode(key)))
    #                                 state_list.append(
    #                                     self.getDeviceStateDictForBoolTrueFalseType(unicode(u"{0}_bool".format(key)),
    #                                                                                 unicode(u"{0}_bool".format(key)),
    #                                                                                 unicode(u"{0}_bool".format(key))))
    #                             else:
    #                                 state_list.append(
    #                                     self.getDeviceStateDictForStringType(unicode(key), unicode(key), unicode(key)))
    #                         except (AttributeError, TypeError, ValueError):
    #                             state_list.append(
    #                                 self.getDeviceStateDictForStringType(unicode(key), unicode(key), unicode(key)))
    #     return state_list
    #
    # def clean_the_keys(self, input_data):
    #     """
    #     Ensure that state names are valid for Indigo
    #     Some dictionaries may have keys that contain problematic characters which
    #     Indigo doesn't like as state names. Let's get those characters out of there.
    #     -----
    #     :param input_data:
    #     """
    #
    #     try:
    #         # Some characters need to be replaced with a valid replacement value because
    #         # simply deleting them could cause problems. Add additional k/v pairs to
    #         # chars_to_replace as needed.
    #
    #         chars_to_replace = {'_ghostxml_': '_', '+': '_plus_', '-': '_minus_', 'true': 'True', 'false': 'False', ' ': '_', ':': '_', '.': '_dot_'}
    #         chars_to_replace = dict((re.escape(k), v) for k, v in chars_to_replace.iteritems())
    #         pattern          = re.compile("|".join(chars_to_replace.keys()))
    #
    #         for key in input_data.iterkeys():
    #             new_key = pattern.sub(lambda m: chars_to_replace[re.escape(m.group(0))], key)
    #             input_data[new_key] = input_data.pop(key)
    #
    #         # Some characters can simply be eliminated. If something here causes problems,
    #         # remove the element from the set and add it to the replacement dict above.
    #         chars_to_remove = {'/', '(', ')'}
    #
    #         for key in input_data.iterkeys():
    #             new_key = ''.join([c for c in key if c not in chars_to_remove])
    #             input_data[new_key] = input_data.pop(key)
    #
    #         # Indigo will not accept device state names that begin with a number, so
    #         # inspect them and prepend any with the string "No_" to force them to
    #         # something that Indigo will accept.
    #         temp_dict = {}
    #
    #         for key in input_data.keys():
    #             if key[0].isdigit():
    #                 temp_dict[u'No_{0}'.format(key)] = input_data[key]
    #             else:
    #                 temp_dict[key] = input_data[key]
    #
    #         input_data = temp_dict
    #
    #         self.finalDict= input_data
    #
    #     except RuntimeError:
    #         pass
    #
    #     except ValueError as sub_error:
    #         self.host_plugin.logger.critical(u'Error cleaning dictionary keys: {0}'.format(sub_error))
    #
    #     except Exception as subError:
    #         # Add wider exception testing to test errors
    #         self.host_plugin.logger.exception(u'General exception: {0}'.format(subError))
### Action Groups

    def action_Simple(self, valuesDict):
        try:

            self.logger.debug(u"clearServerPoweron Time Called as Action.")
            #self.logger.debug(unicode(valuesDict))
            action = valuesDict.pluginTypeId
            device = indigo.devices[valuesDict.deviceId]

            self.logger.debug(u'Action Called:'+unicode(action)+u" and device is "+device.name)

            ipaddress = device.pluginProps.get('ipaddress', "")
            username = device.pluginProps.get('username', "")
            password = device.pluginProps.get('password', "")
            self.logger.debug(u"Connecting to IP " + unicode(ipaddress) + u" with username:" + unicode(
                username) + u" and password:" + unicode(password))
            ilo = hpilo.Ilo(ipaddress, login=username, password=password, timeout=10)
            self.sleep(1)

            if action =="clearPoweronTime":
                ilo.clear_server_power_on_time()
                self.logger.info(u"Clear Power On Time Cleared.")

            if action == "PowerOn":
                ilo.set_host_power(host_power=True)
                self.logger.info(u"Server Power On Sent.")

            if action == "PowerOff":
                ilo.set_host_power(host_power=False)
                self.logger.info(u"Server Power Of Sent.")

            if action == "activateProLicense":
                licensekey = valuesDict.props.get('licensekey','325WC-J9QJ7-495NG-CP7WZ-7GJMM')
                ilo.activate_license(key=str(licensekey))
                self.logger.info(u"Installed Advanced License Key: "+unicode(licensekey))

        except hpilo.IloCommunicationError:
            self.logger.info("Error communicating with HP iLO")
            device.updateStateOnServer('deviceIsOnline', value=False)
            return None
        except hpilo.IloLoginFailed:
            self.logger.info("Login to iLO failed - check Password Username security settings")
            device.updateStateOnServer('deviceIsOnline', value=False)
            return None
        except hpilo.IloFeatureNotSupported:
            self.logger.debug("Some Features not supported. Ignored.")
            pass
        except Exception:
            self.logger.exception("Exception Found")
            device.updateStateOnServer('deviceIsOnline', value=False)
            return None

        return



    ###############################



    def runConcurrentThread(self):


        updateHost = t.time() + 15
        updateHealth = t.time() + 30
        updateFirmware = t.time() + 45
        updatePowerOn = t.time()+20
        updatePower = t.time()+25
        updatePowerStatus = t.time()+1
        loginretry = 0
        try:
            self.sleep(2)
            while True:
                for dev in indigo.devices.itervalues(filter="self"):
                    self.logger.debug("Checking Device:"+unicode(dev.name))

                    if dev.enabled:
                        if t.time() > updatePowerStatus:
                            self.get_the_data_subType(dev, "power_status")
                            updatePowerStatus = t.time() + 60
                        if t.time() > updateHost:
                            self.get_the_data_subType(dev, "hostdata")
                            updateHost = t.time() +60 *60 *4
                        if t.time() > updateHealth:
                            self.get_the_data_subType(dev, "health")
                            updateHealth = t.time() + 60 * 5
                        if t.time() > updateFirmware:
                            self.get_the_data_subType(dev, "fw_version")
                            updateFirmware = t.time() + 60 * 60 * 12
                        if t.time() > updatePowerOn:
                            self.get_the_data_subType(dev, "poweron")
                            updatePowerOn = t.time() + 60 * 60
                        if t.time() > updatePower:
                            self.get_the_data_subType(dev, "power")
                            updatePower = t.time() + 60 * 60

                    self.sleep(5)

                self.sleep(55)

            self.logger.info("Error occurred.  Reconnecting.")

        except self.StopThread:
            self.debugLog(u'Restarting/or error. Stopping thread.')
            pass

        except Exception  as e:
            self.logger.exception("Main RunConcurrent error")

    # def parse_state_values(self, dev):
    #     """
    #     Parse data values to device states
    #     The parse_state_values() method walks through the dict and assigns the
    #     corresponding value to each device state.
    #     -----
    #     :param dev:
    #     """
    #     #
    #     # 2019-12-18 DaveL17 -- Reconfigured to allow for the establishment of other device state types (int, float, bool, etc.)
    #     #
    #     state_list = []
    #     # 2019-01-13 DaveL17 -- excluding standard states.
    #     sorted_list = [_ for _ in sorted(self.finalDict.iterkeys()) if _ not in ('deviceIsOnline', 'parse_error')]
    #
    #     try:
    #         if dev.deviceTypeId == 'MainILO3':
    #             # Parse all values into states as true type.
    #             for key in sorted_list:
    #                 value = self.finalDict[key]
    #                 if isinstance(value, (str, unicode)):
    #                     if value.lower() in ('armed', 'locked', 'on', 'open', 'true', 'up', 'yes'):
    #                         self.finalDict[u"{0}_bool".format(key)] = True
    #                         state_list.append({'key': u"{0}_bool".format(key), 'value': True})
    #                     elif value.lower() in ('closed', 'disarmed', 'down', 'false', 'no', 'off', 'unlocked'):
    #                         self.finalDict[u"{0}_bool".format(key)] = False
    #                         state_list.append({'key': u"{0}_bool".format(key), 'value': False})
    #                 state_list.append(
    #                     {'key': unicode(key), 'value': self.finalDict[key], 'uiValue': self.finalDict[key]})
    #         else:
    #             # Parse all values into states as strings.
    #             for key in sorted_list:
    #                 state_list.append({'key': unicode(key), 'value': unicode(self.finalDict[key]),
    #                                    'uiValue': unicode(self.finalDict[key])})
    #
    #     except ValueError as sub_error:
    #         self.logger.critical(
    #             u"[{0}] Error parsing state values.\n{1}\nReason: {2}".format(dev.name, self.finalDict, sub_error))
    #         dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
    #         state_list.append({'key': 'deviceIsOnline', 'value': False, 'uiValue': "Error"})
    #
    #     except Exception as subError:
    #         # Add wider exception testing to test errors
    #         self.logger.exception(u'General exception: {0}'.format(subError))
    #
    #     dev.updateStatesOnServer(state_list)

    # =============================================================================
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        self.debugLog(u"validateDeviceConfigUi called")
        # User choices look good, so return True (client will then close the dialog window).
        return (True, valuesDict)

    def deviceStartComm(self, device):
        self.logger.debug(u"deviceStartComm called for " + device.name)
        device.stateListOrDisplayStateIdChanged()

        device.updateStateOnServer('deviceIsOnline', value=False)
        device.updateStateOnServer("onOffState", value=False)
        device.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
##

    def shutdown(self):

         self.debugLog(u"shutdown() method called.")

    def startup(self):

        self.debugLog(u"Starting Plugin. startup() method called.")

        # See if there is a plugin update and whether the user wants to be notified.

        # Attempt Socket Connection here


    ## Motion Detected



    def validatePrefsConfigUi(self, valuesDict):

        self.debugLog(u"validatePrefsConfigUi() method called.")

        error_msg_dict = indigo.Dict()

        # self.errorLog(u"Plugin configuration error: ")

        return True, valuesDict




    def refreshDataAction(self, valuesDict):
        """
        The refreshDataAction() method refreshes data for all devices based on
        a plugin menu call.
        """

        self.debugLog(u"refreshDataAction() method called.")
        self.refreshData()
        return True

    def refreshData(self):
        """
        The refreshData() method controls the updating of all plugin
        devices.
        """

        self.debugLog(u"refreshData() method called.")

        try:
            # Check to see if there have been any devices created.
            if indigo.devices.itervalues(filter="self"):

                self.debugLog(u"Updating data...")

                for dev in indigo.devices.itervalues(filter="self"):
                    self.refreshDataForDev(dev)

            else:
                indigo.server.log(u"No Client devices have been created.")

            return True

        except Exception as error:
            self.errorLog(u"Error refreshing devices. Please check settings.")
            self.errorLog(unicode(error.message))
            return False
        # =============================================================================


    def toggleDebugEnabled(self):
        """
        Toggle debug on/off.
        """
        self.debugLog(u"toggleDebugEnabled() method called.")
        if self.logLevel == logging.INFO:
             self.logLevel = logging.DEBUG

             self.indigo_log_handler.setLevel(self.logLevel)
             indigo.server.log(u'Set Logging to DEBUG')
        else:
            self.logLevel = logging.INFO
            indigo.server.log(u'Set Logging to INFO')
            self.indigo_log_handler.setLevel(self.logLevel)

        self.pluginPrefs[u"logLevel"] = self.logLevel
        return

## Triggers

    def triggerStartProcessing(self, trigger):
        self.logger.debug("Adding Trigger %s (%d) - %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
        assert trigger.id not in self.triggers
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.logger.debug("Removing Trigger %s (%d)" % (trigger.name, trigger.id))
        assert trigger.id in self.triggers
        del self.triggers[trigger.id]

    def triggerCheck(self, device, event, partition=0, idofevent=0):
        try:
            for triggerId, trigger in sorted(self.triggers.iteritems()):
                self.logger.debug("Checking Trigger %s (%s), Type: %s" % (trigger.name, trigger.id, trigger.pluginTypeId))

                if trigger.pluginTypeId=="partitionstatuschange" and event=="partitionstatuschange":
                    #self.logger.error("Trigger paritionStatusChange Found: Idofevent:"+unicode(idofevent))
                    #self.logger.error(unicode(trigger))
                    if str(idofevent) in trigger.pluginProps["paritionstatus"]:
                        self.logger.debug("Trigger being run: idofevent: " + unicode(idofevent) + " event: " + unicode(event) )
                        indigo.trigger.execute(trigger)

                if trigger.pluginTypeId=="motion" and event=="motion":
                    if trigger.pluginProps["deviceID"] == str(device.id):
                        self.logger.debug("\tExecuting Trigger %s (%d)" % (trigger.name, trigger.id))
                        indigo.trigger.execute(trigger)
                if trigger.pluginTypeId=="alarmstatus" and event =="alarmstatus":
                    if trigger.pluginProps["zonePartition"] == int(partition):
                        if trigger.pluginProps["alarmstate"] == trigger.pluginProps["deviceID"]:
                            self.logger.debug("\tExecuting Trigger %s (%d)" % (trigger.name, trigger.id))
                            indigo.trigger.execute(trigger)

                    #self.logger.debug("\tUnknown Trigger Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
            return

        except Exception as error:
            self.errorLog(u"Error Trigger. Please check settings.")
            self.errorLog(unicode(error.message))
            return False

