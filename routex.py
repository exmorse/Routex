#!/usr/bin/python

import sys, os, tempfile, time, json
import select
import schedule
import thread
from gcm import *
import smtplib
from socket import *
from email.mime.text import MIMEText
import datetime
import signal
from threading import Lock
import stopit
import bluetooth

import flaskServer
import thingSpeak

# nRF24 
sys.path.append("/home/pi/Documents/pyRadioHeadNRF24")
import pyRadioHeadNRF24 as radio
nrf24 = None

# LoRa - RF95 
sys.path.append("/home/pi/Documents/pyRadioHeadRF95")
import pyRadioHeadRF95 as loradio
rf95 = None


# XBee
from xbee import XBee, ZigBee
import serial
XBEE_PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600
xbee = None
#ser = serial.Serial(PORT, BAUD_RATE)
#xbee = ZigBee(ser, escaped=True)


# WiFi
SOCK_PORT = 5100
s = socket(AF_INET, SOCK_STREAM)
wifi_connection = None
#s.bind(('', port))
#s.listen(3)


# Bluetooth
bt_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
BT_PORT = 0
UUID = "00001101-0000-1000-8000-00805F9B34FB"
bt_connection = None
#bt_sock.bind(("",port))
#bt_sock.listen(1)


# RF 433MHz
import pigpio
sys.path.append("/home/pi/Documents/piVirtualWire")
import piVirtualWire
rx433 = None
tx433 = None


# Technology type constants
NRF24 = "nRF24"
LoRa = "LoRa"
ZIGBEE = "ZigBee"
WIFI = "WiFi"
BLUETOOTH = "Bluetooth"
RF433 = "RF433"


activeTech = {}


# Thread lock to avoid concurrency problem in ZigBee and nRF24
zigbeeLock = Lock()
nrf24Lock = Lock()
loraLock = Lock()
rf433Lock = Lock()
commandFileLock = Lock()
devFileLock = Lock()
servFileLock = Lock()
triggerFileLock = Lock()
scheduleFileLock = Lock()


# ID Counter for Triggers and Schedule
scheduleIdCounter = 0
triggerIdCounter = 0

# Configuration Parameters
SEND_MAIL_ADDRESS = None
SEND_MAIL_PASSWORD = None
THINGSPEAK_USER_KEY = None


def readConfig():
	global UUID, SEND_MAIL_ADDRESS, SEND_MAIL_PASSWORD, THINGSPEAK_USER_KEY

        with open("routex_config.json") as configfile:
                config = json.load(configfile)

	UUID = config['bluetooth_uuid']
	SEND_MAIL_ADDRESS = config['send_mail_address']
	SEND_MAIL_PASSWORD = config['send_mail_password']
	THINGSPEAK_USER_KEY = config['thingspeak_user_key']
	

def releaseLocks(tech):
	print "Releasing tech : " + tech
 
	global zigbeeLock, nrf24Lock, rf433Lock, loraLock

	if tech == ZIGBEE:
		zigbeeLock.release()
	
	if tech == NRF24:
		nrf24Lock.release()
	
	if tech == LoRa:
		loraLock.release()
	
	if tech == RF433:
		print rf433Lock
		rf433Lock.release()


def closeWifiConnection():
	global wifi_connection
	if wifi_connection != None:
		wifi_connection.close()
		wifi_connection = None


def closeBluetoothConnection():
	global bt_connection
	if bt_connection != None:
		bt_connection.close()
		bt_connection = None


def setupTechnologies(techList):
	
	global xbee
	global nrf24
	global rf95
	global s, wifi_connection
	global bt_sock, bt_connection, UUID
	global rx433, tx433

	# To lower case
	techList = map(str.lower, techList)	

	if len(techList) == 0 or ZIGBEE.lower() in techList:
		print "* Using ZigBee"
		ser = serial.Serial(XBEE_PORT, BAUD_RATE)
		xbee = ZigBee(ser, escaped=True)
		activeTech[ZIGBEE] = True
	else:
		activeTech[ZIGBEE] = False

	if len(techList) == 0 or NRF24.lower() in techList:
		print "* Using nRF24"
		nrf24 = radio.nRF24()
		nrf24.managerInit(1) #     1 is my address
		activeTech[NRF24] = True
	else:
		activeTech[NRF24] = False

	if len(techList) == 0 or LoRa.lower() in techList:
		print "* Using LoRa - RF95"
		rf95 = loradio.RF95()
                rf95.init()
                rf95.managerInit(1)
                
                rf95.setFrequency(868)
                rf95.setTxPower(14, False)
                rf95.setSignalBandwidth(rf95.Bandwidth500KHZ)
                rf95.setSpreadingFactor(rf95.SpreadingFactor7)
		activeTech[LoRa] = True
	else:
		activeTech[LoRa] = False

	if len(techList) == 0 or WIFI.lower() in techList:
		print "* Using WiFi"
		s.bind(('', SOCK_PORT))
		s.listen(3)
		activeTech[WIFI] = True
	else:
		activeTech[WIFI] = False

	if len(techList) == 0 or BLUETOOTH.lower() in techList:
		print "* Using Bluetooth"
		bt_sock.bind(('', BT_PORT))
		bt_sock.listen(3)

 		bluetooth.advertise_service(bt_sock, "ExServerService", UUID)
		#print "** Start advertising service"
		activeTech[BLUETOOTH] = True
	else:
		activeTech[BLUETOOTH] = False

	if len(techList) == 0 or RF433.lower() in techList:
		print "* Using RF433"
		pi = pigpio.pi()
		rx433 = piVirtualWire.rx(pi, 2, 500)
		tx433 = piVirtualWire.tx(pi, 3, 500)
		activeTech[RF433] = True
	else:
		activeTech[RF433] = False


def send(tech, dest, msgdata):
        # nRF24
        if tech == NRF24:
		#print "sendtowait --- " + str(msgdata) + " to " + str(dest)
		
		timeout = time.time() + 4
                b = nrf24.sendtoWait(msgdata, len(msgdata), int(dest))
		while b == -1 and timeout > time.time():
                	#print "Resending Ack..."
			#print "sendtowait"
                       	b = nrf24.sendtoWait(msgdata, len(msgdata), int(dest))
                	#print "Passed Resend"	
	
		#print "Returning from send..."	
			
		#print "Time " + str(time.time())
		#print "Timeout was " + str(timeout)

		if timeout < time.time():
			print "Timeout was expired"
			#print "Send result was " + str(b >= 0) 

		return (b >= 0)

        # LoRa - RF95
        if tech == LoRa:
		#print "sendtowait --- " + str(msgdata) + " to " + str(dest)
		
		timeout = time.time() + 5

                time.sleep(0.1)
                b = rf95.sendtoWait(msgdata, len(msgdata), int(dest))
		while b == -1 and timeout > time.time():
                	#print "Resending Ack..."
			#print "sendtowait"
                       	b = rf95.sendtoWait(msgdata, len(msgdata), int(dest))
                	#print "Passed Resend"	
	
		#print "Returning from send..."	
			
		#print "Time " + str(time.time())
		#print "Timeout was " + str(timeout)

		if timeout < time.time():
			print "Timeout was expired"
			#print "Send result was " + str(b >= 0) 

		return (b >= 0)
	
        # RF433
        if tech == RF433:
		global rx433, tx433
                #print "send --- " + str(msgdata) + " to " + str(dest)

		msgAndAddr = "R" + str(dest) + msgdata

		#print "Sending : " + str(msgAndAddr)

                timeout = time.time() + 4
                b = tx433.put(msgAndAddr)
                while b == -1 and timeout > time.time():
                        #print "Resending Ack..."
                        #print "sendtowait"
                        b = tx433.put(msgAndAddr)
                        #print "Passed Resend"

                #print "Returning from send..."

                #print "Time " + str(time.time())
                #print "Timeout was " + str(timeout)

                if timeout < time.time():
                        print "Timeout was expired"
                        #print "Send result was " + str(b >= 0)

                return (b >= 0)
                #return b 

        # ZigBee        
        if tech == ZIGBEE:
                xbee.tx(dest_addr_long=dest.decode('hex'), dest_addr=b'\xFF\xFE', data=msgdata)
                return True

        # WiFi
        global wifi_connection
        if tech == WIFI:

		if msgdata[-1] != '\n':
			msgdata = msgdata + '\n'

		#print "Wifi sending " + msgdata

                if wifi_connection != None:
			#print "Connection not null"
                        wifi_connection.send(msgdata)
			
                else:
                        #print "Need new Connection"
                        print dest
                        wifi_connection = socket(AF_INET, SOCK_STREAM)
                        wifi_connection.connect((dest, 5000))
                        wifi_connection.send(msgdata)

                return True

        # Bluetooth
        global bt_connection, UUID
        if tech == BLUETOOTH:

		if msgdata[-1] != '\n':
			msgdata = msgdata + '\n'

		#print "Bluetooth sending " + msgdata

                if bt_connection != None:
			#print "Connection not null"
                        bt_connection.send(msgdata)
			return True

                else:
                        #print "Need new Connection"
                        print dest
                        bt_connection = bluetooth.BluetoothSocket(bluetooth.RFCOMM)

			print "Finding services..."                        	
			bt_services = bluetooth.find_service(address = dest)
			#print bt_services
			for el in bt_services:
				#print "Service name: " + str(el["name"])
				if el["name"] == getNameFromAddr(BLUETOOTH, dest):	
					#print "* Got it!"
					f_port = el["port"]
					
					bt_connection.connect((dest, f_port))
                        		bt_connection.send(msgdata)

                			return True

			bt_connection = None
			return False

def availableMessage():
        global wifi_connection
	global bt_connection
	global rx433, tx433	
        global nrf24, rf95

	#nRF24
	if activeTech[NRF24]:
        	if nrf24.available():
                	(msg, l, source) = nrf24.recvfromAck()
                	return (True, msg, l, source, NRF24)

	#LoRa - RF95 
	if activeTech[LoRa]:
        	if rf95.available():
                	(msg, l, source) = rf95.recvfromAck()
                	return (True, msg, l, source, LoRa)

	#RF433
	if activeTech[RF433]:
        	if rx433.ready():
			content = rx433.get()
                	msg = ''.join(unichr(e) for e in content)
                	#print "Received Message: " + msg + '\n'
			#print "Source : " + str(msg[0])
			#print "Destination : " + str(msg[1])
			source = str(msg[0])
			dest = str(msg[1])
		
			if dest == 'R':
                		return (True, msg[2:], len(msg[2:]), source, RF433)

			else:
				print "Msg not for me"
		return (False, 0, 0, 0, 0)

        #ZigBee
	if activeTech[ZIGBEE]:
        	with stopit.ThreadingTimeout(1):
			response = xbee.wait_read_frame()
                	if response['id'] != 'rx':
                		return (False, 0, 0, 0, 0)
                	(msg, l, source) = interpretFrame(response)
                	return (True, msg, l, source, ZIGBEE)
	
	#WiFi
	if activeTech[WIFI]:
		read_list = [s]
		readable, writable, errored = select.select(read_list, [], [], 1)
		for sock in readable:
			#print "---New Socket"
			wifi_connection, (dev_address, dev_port) = sock.accept()
        		#print "Receiving input from : " + str(dev_address) + str(dev_port)
        		
			ready = select.select([wifi_connection], [], [], 4)
			if ready[0]:
				#print "Got something"
				msg = wifi_connection.recv(200)
        			l = len(msg)
        			return (True, msg, l, dev_address, WIFI)
			else:
				print "Timeout"

	#Bluetooth
	if activeTech[BLUETOOTH]:
		read_list = [bt_sock]
		readable, writable, errored = select.select(read_list, [], [], 1)
		for sock in readable:
			#print "---New Socket"
			bt_connection, (dev_address, dev_port) = sock.accept()
        		#print "Receiving input from : " + str(dev_address) + str(dev_port)     		
			ready = select.select([bt_connection], [], [], 4)
			if ready[0]:
				#print "Got something"
				msg = bt_connection.recv(200)
        			l = len(msg)
        			return (True, msg, l, dev_address, BLUETOOTH)
			else:
				print "Timeout"

        # No message
        return (False, 0, 0, 0, 0)


def receiveMessageTech(tech, expectedSource):
        if tech == NRF24:
                if nrf24.available():
                        (msg, l, source) = nrf24.recvfromAck()
			if (str(source) == str(expectedSource)):
                        	return (True, msg, l, source)
                else:
                        return (False, 0, 0, 0)

        if tech == LoRa:
                if rf95.available():
                        (msg, l, source) = rf95.recvfromAck()
			if (str(source) == str(expectedSource)):
                        	return (True, msg, l, source)
                else:
                        return (False, 0, 0, 0)

        if tech == RF433:
		if rx433.ready():
                        content = rx433.get()
                        msg = ''.join(unichr(e) for e in content)
                        #print "Received Message: " + msg + '\n'
			#print "Source : " + str(msg[0])
			#print "Destination : " + str(msg[1])
			source = str(msg[0])
			dest = str(msg[1])
		
			if dest == 'R' and str(source) == str(expectedSource):
                        	return (True, msg[2:], len(msg[2:]), source)

			else:
				print "Msg not for me"
		else:
                        return (False, 0, 0, 0)


        if tech == ZIGBEE:
		with stopit.ThreadingTimeout(1):
                	response = xbee.wait_read_frame()
                	
			if response['id'] != 'rx':
                		return (False, 0, 0, 0)
                	(msg, l, source) = interpretFrame(response)
		
			#print "Source " + str(source) 
			#print "Expected Source " + str(expectedSource) 
	
			if (str(source) == str(expectedSource)):
                		return (True, msg, l, source)

        if tech == WIFI:
        	#print "Receiving input from present connection"
        		
		ready = select.select([wifi_connection], [], [], 4)
		if ready[0]:
			#print "Got something"
			msg = wifi_connection.recv(200)
        		l = len(msg)
        		return (True, msg, l, True)
		else:
			print "Timeout"
	
        if tech == BLUETOOTH:
        	#print "Receiving input from present connection"
        		
		ready = select.select([bt_connection], [], [], 4)
		if ready[0]:
			#print "Got something"
			msg = bt_connection.recv(200)
        		l = len(msg)
        		return (True, msg, l, True)
		else:
			print "Timeout"

	return (False, 0, 0, 0)


def readDeviceFromFile():
	devs = []
        
	devFileLock.acquire()
        with open("devs.json") as devfile:
                devs = json.load(devfile)
        devFileLock.release()

	return devs


def writeDevicesToFile():
	#print "Writing to file"
	old = os.umask(011)

	#print "About to write: " + str(devs)

	devFileLock.acquire()
	with open(filename, 'w+') as outfile:
    		json.dump(devs, outfile)
	devFileLock.release()

	os.umask(old)
	#print "Wrote!"


def readServiceData():
	filename = "service_data.json"

	service_data = []

	servFileLock.acquire()
        with open(filename) as data_file:
                service_data = json.load(data_file)
	servFileLock.release()	

	return service_data


def readTriggersFromFile():
	filename = "trigger_events.json"

	trigs = []

	triggerFileLock.acquire()
        with open(filename) as trig_file:
                trigs = json.load(trig_file)
	triggerFileLock.release()	

	return trigs


def readScheduleFromFile():
	filename = "scheduled_events.json"

	sched = []

	scheduleFileLock.acquire()
        with open(filename) as sched_file:
                sched = json.load(sched_file)
	scheduleFileLock.release()	

	return sched


def writeTriggersToFile(trigs):
	filename = "trigger_events.json"

	triggerFileLock.acquire()
        with open(filename, 'w+') as trig_file:
                trig_file.write(json.dumps(trigs))
	triggerFileLock.release()	


def getNameFromAddr(tech, addr):
	devs = readDeviceFromFile()

        for dev in devs:
                if dev["technology"] == tech and dev["address"] == addr:
                        return dev["device_name"]

        return ""



def getRequestType(msg):
	return msg[0]


def getInfoFromJoinRequest(msg):
        c = '!'
        separatorPositions = [pos for pos, char in enumerate(msg) if char == c]
        requestType = msg[0]
        deviceName = msg[separatorPositions[0]+1:separatorPositions[1]]
        alwaysOnChar = msg[separatorPositions[1]+1]
	
	if alwaysOnChar == 'A':
		alwaysOn = True
	else:
		alwaysOn = False
    
        print requestType
        print deviceName
        return (requestType, deviceName, alwaysOn)


def handleJoinRequest(devName, alwaysOn, source, tech):
        if source == 0:
                        print "Receive Problem... Need to Retry"
        else:
                jack = "J" + ack
                timeout = time.time() + 5
                b = send(tech, source, jack)
		print "Send -->" + str(b)
                if b:
                        print "Device Registered Successfully"
			#print "Device is not always on"

                        dev = {}
                        toAdd = True

                        for elem in devs:
                                if elem["device_name"] == devName:
                                        dev = elem
                                        toAdd = False

                        dev["device_name"] = devName
                        dev["technology"] = tech
                        dev["address"] = source
			dev["always_on"] = alwaysOn
                        
			if toAdd:
				servs = []
                        	dev["services"] = servs
                                devs.append(dev)
                        
				# If name is already present override address! 
				# (Useful for wifi in not-always-on mode)

			print devs
                        writeDevicesToFile()

			if tech == WIFI:
				closeWifiConnection()			

			if tech == BLUETOOTH:
				closeBluetoothConnection()			

                        return 1

                else:
                        print "Failed, Need to Retry"


def removeDevice(devName):
	global devs
	devs = readDeviceFromFile()
	
	for i, dev in enumerate(devs):
		if dev["device_name"] == devName:
			print "Found device to remove!"

			del devs[i]
			writeDevicesToFile()

			return True

	return False


def getInfoFromServiceRequest(msg, tech):
        c = '!'
        status = True
        separatorPositions = [pos for pos, char in enumerate(msg) if char == c]
        if len(separatorPositions) != 3:

                # Case of extra DONE message
                dack = "S!DONE!Ok"
                if msg == "S!DONE":
                        send(tech, source, dack)

                status = False
                return (None, None, None, None, status)

        requestType = msg[0]
        serviceRequestType = msg[2]
        serviceType = msg[4]
        serviceName = msg[separatorPositions[2]+1:]

        return (requestType, serviceRequestType, serviceType, serviceName, status)


def handleServiceRequest(msg, source, tech):
        (r, serviceRequestType, serviceType, serviceName, status) = getInfoFromServiceRequest(msg, tech, source)

        if status is False:
                print "Bad Request Format"
                return -1

        dev = {}

        for elem in devs:
                if elem["address"] == source:
                        dev = elem
                        print "Device Found"

        if dev == {}:
                print "Device not registered"
                return False

        if source == 0:
                        print "Receive Problem... Need to Retry"
        else:
                # Add Service
                if serviceRequestType == "A":
                        print "---Add Service Request---"
                        return addService(serviceName, serviceType, dev, source, tech)
	
		# Service Data Update
		if serviceRequestType == "U":
			print "---Service Data Update---"
			return acceptServiceDataUpdate(tech, source, serviceName)


def getInfoFromCommandRequest(msg):
	c = '!'
        status = True
        separatorPositions = [pos for pos, char in enumerate(msg) if char == c]
        if len(separatorPositions) != 2:
                status = False
        commandType = msg[2]
        commandName = msg[separatorPositions[1]+1:]
	
	if commandType == 'B':
		commandType = "Button"
	elif commandType == 'I' or commandType == 'N':
		commandType = "Button_Int"

        return (commandType, commandName, status)


def addService(serviceName, serviceType, dev, source, tech):
        print "----Service--"
        gack = "S!G!Ok"
	expectedSource = source

        ServTypes = {}
        ServTypes["N"] = "Number"
        ServTypes["T"] = "Text"
        ServTypes["S"] = "Status"

	if tech == ZIGBEE:
		zigbeeLock.acquire()

	if tech == NRF24:
		nrf24Lock.acquire()

	if tech == LoRa:
		loraLock.acquire()

	if tech == RF433:
		rf433Lock.acquire()

        b = send(tech, source, gack)

        if b:
                serv = {}
                toAdd = True
                servs = dev["services"]

                for elem in servs:
                        if elem["service_name"] == serviceName:
                                serv = elem
                                print "Service Already Present"
                                toAdd = False

                serv["service_name"] = serviceName
                serv["service_type"] = ServTypes[serviceType]
                serv["thingspeak_set"] = False
		serv["thingspeak_on"] = False

                if toAdd:
                        servs.append(serv)

                dev["services"] = servs
                #print devs

                print "Waiting for " + serviceName + " commands or Done"

                done = False
                dack = "S!DONE!Ok"
                commands = []
                serv["commands"] = commands

                # Default "Get" Command if Service has a value to return 
                if serviceType == 'T' or serviceType == 'N':
                        command = {}
                        command["command_name"] = "Get"
                        command["command_type"] = "Button"
                        serv["commands"].append(command)

                while not done:
                        (isAvailable, msg, l, source) = receiveMessageTech(tech, expectedSource)
                        if isAvailable:
                                # DONE Message
                                if msg == "S!DONE":
                                        b = send(tech, source, dack)
                                        if b:
                                                done = True
                                        done = True
                                # Add Command
                                else:
                                        cack = "C!Added"
                                        (commandType, commandName, status) = getInfoFromCommandRequest(msg)

                                        if status == False:
                                                break

                                        else:
                                                command = {}
                                                command["command_name"] = commandName
                                                command["command_type"] = commandType

                                                toAdd = True
                                                for elem in serv["commands"]:
                                                        if elem["command_name"] == commandName:
                                                                toAdd = False

                                                if toAdd:
                                                        serv["commands"].append(command)

                                                #print "COMMAND: " + str(command)

                                                send(tech, source, cack)
		
                releaseLocks(tech)

		if tech == WIFI:
			closeWifiConnection()			

		if tech == BLUETOOTH:
			closeBluetoothConnection()			

		#print "---Done"
                writeDevicesToFile()
                return 1

        else:
                print "Failed, Need to Retry"
	 

def writeCommandToFile(tech, addr, servName, command, arg):
	commandFileLock.acquire()
	with open("stored_commands.json") as commandFile:
		comJson = json.load(commandFile)
	commandFileLock.release()

	print comJson

	com = {}
	com["technology"] = tech
	com["address"] = addr
	com["service_name"] = servName
	com["command"] = command
	com["argument"] = arg
	comJson.append(com)

	print comJson

	commandFileLock.acquire()
	with open("stored_commands.json", "w+") as commandFile:
		commandFile.write(json.dumps(comJson))
	commandFileLock.release()


def executeCommandFromParams(devName, tech, addr, servName, command, arg, ignoreAlwaysOn):
	global zigbeeLock
	global nrf24Lock
	global loraLock
	global rf433Lock
	global wifi_connection

	# --- Always On Check ---
	if ignoreAlwaysOn != True:
		devs = readDeviceFromFile()

		for dev in devs:
			#print str(dev)	
			#print dev["technology"]
			#print dev["address"]
			#print dev["always_on"]
			if dev["technology"] == str(tech) and str(dev["address"]) == str(addr):
				if dev["always_on"] == False:

					writeCommandToFile(tech, addr, servName, command, arg)

					return "Stored"

	# --- End Always On Check ---

	if tech == ZIGBEE:
		zigbeeLock.acquire()

	if tech == NRF24:
		nrf24Lock.acquire()

	if tech == LoRa:
		loraLock.acquire()

	if tech == RF433:
		rf433Lock.acquire()

	if arg == '' or arg == None or arg == 'None': 
       		msg = str(servName) + "!" + str(command)
              	print "Sending " + msg
		send(tech, addr, msg)	
		print "Sent"		
	#Send with Args
	else:
       		msg = str(servName) + "!" + str(command) + '*'
               	print "Sending " + msg
		send(tech, addr, msg)	


		if tech == RF433:
			#print "Tech rf433, waiting"
			toAckCom = True
			timeout = time.time() + 5
			while toAckCom:
				(isAvailable, msg, l, source) = receiveMessageTech(tech, addr)
				if isAvailable:
					if msg == "OK!ARG":
						#print "Got ack... (RF433)"
						toAckCom = False
			
				if toAckCom and time.time() > timeout:
					print "Timeout Expired"
					return False	
				
		print "Sent command, now sending arg"
                
		wifi_connection = None

		time.sleep(0.5)
	
		msg = '*!' + str(arg)	
               	#print "Sending " + msg
		send(tech, addr, msg)	
		#print "Sent arg"
			
	# Receive 
        timeout = time.time() + 5
        toAck = True

	if tech == BLUETOOTH and bt_connection == None:
		return "No Ack"

        while toAck:
		(isAvailable, msg, l, source) = receiveMessageTech(tech, addr)
                if isAvailable:
                	try:
                        	if msg[0] != 'R' and msg[1] != '!':
                                	return False
                        except IndexError:
                        	return False

			releaseLocks(tech)	
		
			msg = msg[2:] 
			print "Received " + msg
                	toAck = False
				
			# If ThingSpeak is active, post the result
			checkThingSpeak(devName, servName, msg)
							
			result = msg
	
			# Write to file!
			if result != "No Ack" and result != '':
        			#Write data on file
				#print "Write to file..."
				
				service_data = readServiceData()
			
        			found = False
        			for el in service_data:
                			if el["device_name"] == devName:
                        			if el["service_name"] == servName:
                               				found = True
                               				value_list = el["values"]

	        		if not found:
        	        		new_service = {}
                			new_service["device_name"] = devName
                			new_service["service_name"] = servName
                			new_service["values"] = []
                			value_list = new_service["values"]
                			service_data.append(new_service)

				millis = str(int(round(time.time() * 1000)))
       				newvalue = {}
       				newvalue["value"] = msg
       				newvalue["timestamp"] = millis
       				value_list.append(newvalue)

				servFileLock.acquire()
       				with open('service_data.json', 'w+') as outfile:
               				json.dump(service_data, outfile)
				servFileLock.release()

				#print "Wrote to file!"
				
				# Check Active Triggers
				##if command == "Get":		
				thread.start_new_thread(checkForTrigger, (devName, servName, msg))


		if time.time() > timeout:
        		print "Timeout Expired"
	
			if tech == WIFI:
				closeWifiConnection()

			if tech == BLUETOOTH:
				closeBluetoothConnection()

			releaseLocks(tech)	

        		toAck = False
			return "No Ack"

	
	if tech == WIFI:
		closeWifiConnection()

	if tech == BLUETOOTH:
		closeBluetoothConnection()

	#print "Returning : " + msg

	return msg


def checkForTrigger(devName, servName, result):
	#print "TRIGGER : ", devName, servName, result
	
	with open('trigger_events.json') as trigFile:
                trigs = json.load(trigFile)

	trigDone = False
	
	for trig in trigs:
		trigDone = False
		for condEl in trig["conditions"]:
			if condEl["device_name"] == devName and condEl["service_name"] == servName and not trigDone:
				print "Found trigger to evaluate"
				trigDone = True
				# Evaluating Trigger Condition
				toExec = True
				print trig["conditions"]
				for condToEvaluate in trig["conditions"]:
					print condToEvaluate
					if evaluateCondition(condToEvaluate) == False:
						toExec = False
						break

				if toExec:
					print "Executing trigger action"
					executeTriggerAction(trig["then"])


def getLastValue(devName, servName):
	service_data = readServiceData()

	values = []

        for el in service_data:
                if el["device_name"] == devName and el["service_name"] == servName:
                        values = el["values"]

        if values == [] or len(values) == 0:
                return None

        else:
                values = sorted(values, key=lambda k: k['timestamp'])
                return values[-1]["value"]


def evaluateCondition(triggerCondition):
	#print "Evaluating condition"
	
	condition = str(triggerCondition["condition"])
	value = triggerCondition["value"]
	devName = triggerCondition["device_name"]	
	servName = triggerCondition["service_name"]	
	result = getLastValue(devName, servName)

	#print devName, servName, condition, value, result
	
	if result == None:
		return False
	
	try:
		if condition == "greater":	
			print "greater"
			result = float(result)
			value = float(value)
			if result > value:
				return True

		if condition == "less":
			result = float(result)
			value = float(value)
			if result < value:
				return True

		if condition == "equal":
			result = float(result)
			value = float(value)
			if result == value:
				return True
	
		if condition == "matches":
			result = str(result)
			value = str(value)
			if result == value:
				return True
		
		if condition == "contains":
			result = str(result)
			value = str(value)
			if value in result:
				return True

		return False
	
	except ValueError:
		return False

		
def executeTriggerAction(then):
	print "Executing trigger..."
	actionType = then["type"]
	
	if actionType == "command":
		devName = then["device_name"]
		servName = then["service_name"]
		command = then["command"]

		if "argument" in then.keys():
			argument = then["argument"]
		else:
			argument = None

		#print "Should execute ", devName, servName, command
		
		devs = readDeviceFromFile()

		dev = {}
		for elem in devs:
        		if elem["device_name"] == devName:
                		dev = elem

		if dev == {}:
        		print "Device Not Found"
			return False

		tech = dev["technology"]
		address = dev["address"]

		time.sleep(0.4)
		executeCommandFromParams(devName, tech, address, servName, command, argument, False)

	elif actionType == "notification":
		gcm = GCM("AIzaSyBWxn7eSxFS3h0W_8lnip6JM3lnkPcMGqc")
		reg_id = then["notification_id"]
		text_content = then["text_content"]
		#data = {'message': devName + ' - ' + servName + ' - ' + str(result) }
		data = {'message': 'Trigger - ' + text_content} 
		gcm.plaintext_request(registration_id=reg_id, data=data)
	
	elif actionType == "mail":
		print "Sending Mail"
		to = then["mail_address"]
		user = str(SEND_MAIL_ADDRESS)
		password = str(SEND_MAIL_PASSWORD)
		smtpserver = smtplib.SMTP('smtp.live.com', 587)
		smtpserver.ehlo()
		smtpserver.starttls()
		smtpserver.ehlo
		smtpserver.login(user, password)
		today = datetime.date.today()
		#text = devName + ' - ' + servName + ' - ' + str(result)
		#text = str(then)
		text_content = then["text_content"]
		msg = MIMEText(text_content)
		msg['Subject'] = 'Trigger on  %s' % today.strftime('%b %d %Y')
		msg['From'] = user
		msg['To'] = to
		smtpserver.sendmail(user, [to], msg.as_string())
		smtpserver.quit()
			
	print "Done"

	
def schedulingThread():
	#print "Thread: Started"
	while True:
		schedule.run_pending()
		time.sleep(5)


def scheduleUpdate(schedType, deviceName, serviceName, command, argument, timeType, freq_or_time):
	global scheduleIdCounter        

	# Check for data on the pipe
	schedFile = open("scheduled_events.json")
	schedJson = json.load(schedFile)	
	schedFile.close()	


	print (schedType, deviceName, serviceName, command, argument, timeType, freq_or_time)
	dev = {}
	if schedType == 'A':
		for el in devs:
			if el["device_name"] == deviceName:
				dev = el		
	
			if dev == {}:
				print "No matching device found"	
				return False

	if schedType == 'A':
		schedEl = {}
		#for el in schedJson:
			#if el["device_name"] == deviceName and el["service_name"] == serviceName and el["command"] == command:
			#	print "Command Already Present"
			#	return False

		schedEl["device_name"] = deviceName
		schedEl["service_name"] = serviceName
		schedEl["command"] = command
		schedEl["time_type"] = timeType
		schedEl["id"] = scheduleIdCounter
		scheduleIdCounter = scheduleIdCounter + 1

		if timeType == "F":
			schedEl["frequency"] = freq_or_time
		else:
			schedEl["time"] = freq_or_time
		schedEl["argument"] = argument
		schedJson.append(schedEl)
		
		with open("scheduled_events.json", "w+") as outFile:
			outFile.write(json.dumps(schedJson))

		#key = deviceName + '!' + serviceName + '!' + command	
		key = schedEl["id"]
		#Add to job dictionary, in order to be able to remove the job
		if (timeType == "F"):
			scheduledJobDict[key] = schedule.every(int(freq_or_time)).seconds.do(
			executeCommandFromParams, dev["device_name"], dev["technology"], dev["address"], serviceName, command, argument, False)

		else:
			scheduledJobDict[key] = schedule.every().day.at(freq_or_time).do(
			executeCommandFromParams, dev["device_name"], dev["technology"], dev["address"], serviceName, command, argument, False)
		
		print "Added Successfully!"

	if schedType == 'R':
		print 'Removing...'
		#key = deviceName + '!' + serviceName + '!' + command
		key = argument
		if key in scheduledJobDict.keys():
			print "Present in jobs"
			schedule.cancel_job(scheduledJobDict[key])
			del scheduledJobDict[key]

			# Remove from file
			schedEl = {}
			index = -1
                        for i, el in enumerate(schedJson):
		                #if el["device_name"] == deviceName and el["service_name"] == serviceName and el["command"] == command:
                                if el["id"] == argument: 
				      	print "Found in File"
					schedEl = el
					index = i
					break
                                            
			if schedEl == {}:	
				print "Failed to Remove From File"
				return
					
			del schedJson[i]	

			with open("scheduled_events.json", "w+") as outFile:
                               	outFile.write(json.dumps(schedJson))

			print "Removed"

		else:
			print "Schedule Element not Found"


def sendStoredCommands(tech, addr):
	commandFileLock.acquire()
	with open("stored_commands.json") as comFile:
		comJson = json.load(comFile)
	commandFileLock.release()

	print comJson

	if tech == BLUETOOTH:
		closeBluetoothConnection()

	delIndex = []

	for index, com in enumerate(comJson):
		if com["technology"] == tech and str(com["address"]) == str(addr):
			#print "Should send..."
			
			print com["technology"]
			print com["address"]
			servName = com["service_name"]
			print servName
			command = com["command"]
			print command
			argument = com["argument"]
			print argument

			executeCommandFromParams(getNameFromAddr(tech, addr), tech, addr, servName, command, str(argument), True)
			
			if tech == BLUETOOTH:
				closeBluetoothConnection()
			
			#del comJson[index]
			delIndex.append(index)	

	# Remove elements
	for i in sorted(delIndex, reverse=True): 
		del comJson[i]

	
	commandFileLock.acquire()
	with open("stored_commands.json", "w+") as outFile:
		outFile.write(json.dumps(comJson))
	commandFileLock.release()

	#print "Sending finished..."
	send(tech, addr, "W!FINISHED")
	#print "Sent finished!"

	#if tech == BLUETOOTH:
	#	closeBluetoothConnection()
			

def setServiceThingSpeak(devName, servName, command):
	global devs
	devs = readDeviceFromFile()

	print devName
	print servName
	print command

	for dev in devs:
		if dev["device_name"] == devName:
        		for serv in dev["services"]:
				print serv["service_name"]
				if serv["service_name"] == servName:	
					if command == "GET":
						return serv["thingspeak_on"]

					if command == "OFF":
						serv['thingspeak_on'] = False
					
					if command == "ON":
						if serv['thingspeak_set'] == False:
							key = thingSpeak.createChannel(devName, servName, THINGSPEAK_USER_KEY)
							if key == False:
								return -1

							serv['thingspeak_key'] = key

						serv['thingspeak_on'] = True

					writeDevicesToFile()
	
					return 1

	return -1


def checkThingSpeak(devName, servName, result):
	devs = readDeviceFromFile()

	for dev in devs:
                if dev["device_name"] == devName:
                        for serv in dev["services"]:
                                if serv["service_name"] == servName:
                                	if serv["thingspeak_on"]:
						thingSpeak.addData(serv["thingspeak_key"], result)



def getRequestType(msg):
	return msg[0]


def acceptServiceDataUpdate(tech, addr, servName):
	devName = getNameFromAddr(tech, addr)
	
	if devName == None:
		print "Device Not Found"

	#print "Device Name --> " + devName

	if tech == ZIGBEE:
		zigbeeLock.acquire()

	if tech == NRF24:
		nrf24Lock.acquire()

	if tech == LoRa:
		loraLock.acquire()

	if tech == RF433:
		rf433Lock.acquire()

	uack = "S!U!Ok"
	ret = send(tech, addr, uack)

	# TODO Check if service exists

	# Receive 
        timeout = time.time() + 5
        toAck = True

	if tech == BLUETOOTH and bt_connection == None:
		return "No Ack"

        while toAck:
		(isAvailable, msg, l, source) = receiveMessageTech(tech, addr)
                if isAvailable:
                	try:
                        	if msg[0] != 'R' and msg[1] != '!':
                                	return False
                        except IndexError:
                        	return False

			releaseLocks(tech)	
		
			msg = msg[2:] 
			print "Received " + msg
                	toAck = False
				
			# If ThingSpeak is active, post the result
			checkThingSpeak(devName, servName, msg)
							
			result = msg
	
			# Write to file!
			if result != "No Ack" and result != '':
        			#Write data on file
				#print "Write to file..."
				
				service_data = readServiceData()
			
        			found = False
        			for el in service_data:
                			if el["device_name"] == devName:
                        			if el["service_name"] == servName:
                               				found = True
                               				value_list = el["values"]

	        		if not found:
        	        		new_service = {}
                			new_service["device_name"] = devName
                			new_service["service_name"] = servName
                			new_service["values"] = []
                			value_list = new_service["values"]
                			service_data.append(new_service)

				millis = str(int(round(time.time() * 1000)))
       				newvalue = {}
       				newvalue["value"] = msg
       				newvalue["timestamp"] = millis
       				value_list.append(newvalue)

				servFileLock.acquire()
       				with open('service_data.json', 'w+') as outfile:
               				json.dump(service_data, outfile)
				servFileLock.release()

				#print "Wrote to file!"
				
				# Check Active Triggers
				##if command == "Get":		
				thread.start_new_thread(checkForTrigger, (devName, servName, msg))


		if time.time() > timeout:
        		print "Timeout Expired"
	
			if tech == WIFI:
				closeWifiConnection()

			if tech == BLUETOOTH:
				closeBluetoothConnection()

			releaseLocks(tech)	

        		toAck = False
			return "No Ack"

	
	if tech == WIFI:
		closeWifiConnection()

	if tech == BLUETOOTH:
		closeBluetoothConnection()

	print "Done!"




def getInfoFromJoinRequest(msg):
        c = '!'
        separatorPositions = [pos for pos, char in enumerate(msg) if char == c]
        requestType = msg[0]
        deviceName = msg[separatorPositions[0]+1:separatorPositions[1]]
        alwaysOnChar = msg[separatorPositions[1]+1]
	
	if alwaysOnChar == 'A':
		alwaysOn = True
	else:
		alwaysOn = False

        return (requestType, deviceName, alwaysOn)


def getInfoFromServiceRequest(msg, tech, source):
        c = '!'
        status = True
        separatorPositions = [pos for pos, char in enumerate(msg) if char == c]
        if len(separatorPositions) != 3:

                dack = "S!DONE!Ok"
                # Case of extra DONE message
                if msg == "S!DONE":
                        send(tech, source, dack)

                	status = False
                	return (None, None, None, None, status)
                
		# Case of Service Data Update --> S!U!ServName
		if len(separatorPositions) == 2:
			requestType = msg[0]		
        		serviceRequestType = msg[2]
			if serviceRequestType == 'U':
				serviceName = msg[separatorPositions[1]+1:]
				return (requestType, serviceRequestType, '', serviceName, True)

		status = False
                return (None, None, None, None, status)

        requestType = msg[0]
        serviceRequestType = msg[2]
        serviceType = msg[4]
        serviceName = msg[separatorPositions[2]+1:]

        return (requestType, serviceRequestType, serviceType, serviceName, status)


def interpretFrame(frame):
	msg = frame['rf_data'].split('\0')[0]
	l = len(msg)
	source = frame['source_addr_long'].encode('hex')
	return (msg, l, source)


def mainLoop():
        while True:
                zigbeeLock.acquire()
                nrf24Lock.acquire()
                loraLock.acquire()
                rf433Lock.acquire()
                # Receive Requests
                (isAvailable, msg, l, source, tech) = availableMessage()
                zigbeeLock.release()
                nrf24Lock.release()
                loraLock.release()
                rf433Lock.release()

                if isAvailable:
                        r = getRequestType(msg)
                        if r == 'J':
				print "--Join Request"
                                (r, d, alwaysOn) = getInfoFromJoinRequest(msg)
                                handleJoinRequest(d, alwaysOn, source, tech)
                        if r == 'S':
				print "--Service Request"
                                handleServiceRequest(msg, source, tech)
			if r == 'W':
				print "--Device Awake" + str(tech)
				closeWifiConnection()
				#time.sleep(1)
				sendStoredCommands(tech, source)
				closeWifiConnection()
                time.sleep(0.3)

		
# --- Main ---
if __name__ == "__main__":

	readConfig()

	ack = "!Ok"
	filename = "devs.json"
	devs = []
	writeDevicesToFile()

	# Dictionary used to store and delete schedule events
	scheduledJobDict = {}

	#Write [] on trigger file
	with open("trigger_events.json", "w+") as outFile:
		outFile.write(json.dumps([]))

	#Write [] on schedule file
	with open("scheduled_events.json", "w+") as outFile:
		outFile.write(json.dumps([]))

	#Write [] on schedule file
	with open("stored_commands.json", "w+") as outFile:
		outFile.write(json.dumps([]))

	# Setup active technologies
	del(sys.argv[0])
	print sys.argv
	setupTechnologies(sys.argv)

	# Schedule and Flask threads
	t1 = thread.start_new_thread(schedulingThread, ())
	t2 = thread.start_new_thread(flaskServer.startFlaskServer, (executeCommandFromParams, scheduleUpdate, setServiceThingSpeak, readDeviceFromFile, readServiceData, removeDevice, readTriggersFromFile, writeTriggersToFile, readScheduleFromFile))

	# Main 	
	mainLoop()
