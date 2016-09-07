#!/usr/bin/python

import sys, os, time, tempfile, datetime
from flask import Flask, request, json

from flask_cors import CORS, cross_origin


app = Flask(__name__)
CORS(app)


# Callback function to call 
ecfp = None 		# executeCommandFromParams
su = None 		# scheduleUpdate
tse = None 		# thingSpeakEnable (setServiceThingSpeak)
rdff = None		# readDeviceFromFile
rsd = None		# readServiceData
rd = None 		# removeDevice
rtff = None		# readTriggersFromFile
wttf = None		# writeTriggerToFile
rsff = None		# readScheduleFromFile

jsonObject = { 
        "status" : "Ok",
        "devices": [
                {
                "name": "Arduino-1",
                "hardware": "Arduino",
                "technology": "nRF24"
                }
        ]
} 

@app.route("/getDevices.py", methods = ['GET'])
def get_devices():
	print "---Get Devices---"
	filename = "devs.json"

	print "-Opening device file"

	#with open(filename) as data_file:
    	#	devs = json.load(data_file)

	devs = rdff()

	print "-Read devices"
	
	jsonCurrent = {}
	jsonCurrent["status"] = "Ok"
	jsonCurrent["devices"] = devs

	print "-Returning"

	return json.dumps(jsonCurrent)


@app.route("/getLastValue.py", methods = ['GET', 'POST'])
def get_last_value():
        print "---Get Last Value of Service"
    
        data = request.get_json()

        deviceName = data["device_name"]
        serviceName = data["service_name"]

	service_data = rsd()

        values = []

        for el in service_data:
                if el["device_name"] == deviceName and el["service_name"] == serviceName:
                        values = el["values"]

        jsonCurrent = {}
        jsonCurrent["device_name"] = deviceName
        jsonCurrent["service_name"] = serviceName
    
        if values == [] or len(values) == 0:
                jsonCurrent["available"] = False
    
        else:
                values = sorted(values, key=lambda k: k['timestamp'])
    
                jsonCurrent["available"] = True
                jsonCurrent["value"] = values[-1]["value"]
                jsonCurrent["timestamp"] = datetime.datetime.fromtimestamp(long(values[-1]["timestamp"])/1000).strftime("%Y-%m-%d %H:%M")

        return json.dumps(jsonCurrent)


@app.route("/getDeviceInfo.py", methods = ['GET', 'POST'])
def get_device_info():
	print "---Get Device Info---"

	err = open("/tmp/err.out", "w")
	original_stderr = sys.stderr
	sys.stderr = err 

	string = "Ok"

	filename = "devs.json" 
	
	data = request.get_json()
	
	device_name = data["device_name"]
	
	with open(filename) as data_file:    
		devs = json.load(data_file)

	d = None
	for elem in devs:
        	if elem["device_name"] == device_name:
                	d = elem

	jsonCurrent = {}
	jsonCurrent["device_name"] = d["device_name"]
	jsonCurrent["status"] = "Ok"
	jsonCurrent["services"] = d["services"]

	print "-Returning"

	return json.dumps(jsonCurrent)


@app.route("/executeCommand.py", methods = ['GET', 'POST'])
def execute_command():
	print "---Execute Command---"

	err = open("/tmp/err.out", "w")
	original_stderr = sys.stderr
	sys.stderr = err 

	data = request.get_json()

	result = "Error"

	devfilename = "devs.json"
	with open(devfilename) as data_file:
    		devs = json.load(data_file)
	
	if data is None:
	        string = "Data is None"

	else:
        	string = str(len(data))
        	device_name = data["device_name"]
        	service_name = data["service_name"]
        	command = data["command"]
        	argument = None
        
		if "argument" in data.keys():
			#print "Got argument"
                	argument = data["argument"]

	dev = {}
	for elem in devs:
        	if elem["device_name"] == device_name:
                	dev = elem

	tech = dev["technology"]
	address = dev["address"]

	if argument == None:
		commandString = device_name + '!' + tech + '!' + str(address) + '!' + service_name + '!' +  command + '!'
	else:
		commandString = device_name + '!' + tech + '!' + str(address) + '!' + service_name + '!' +  command + '!' + argument


	#print commandString
	
	result = ecfp(device_name, tech, address, service_name, command, argument, False)

	print "Returned " + result

	millis = str(int(round(time.time() * 1000)))

	jsonObject = {
        	"device_name": device_name,
        	"result": result,
        	"timestamp": millis,
		"timestamp_str": datetime.datetime.fromtimestamp(long(millis)/1000).strftime("%Y-%m-%d %H:%M")
	}

	return json.dumps(jsonObject)


@app.route("/getSchedule.py", methods = ['GET', 'POST'])
def get_schedule():
	print "---Get Schedule--"
	data = request.get_json()

	err = open("/tmp/err.out", "w")
	original_stderr = sys.stderr
	sys.stderr = err
	
	device_name = data["device_name"]
	service_name = data["service_name"]

	schedList = []
	
	schedJson = rsff()

	for el in schedJson:
        	if el["device_name"] == device_name and el["service_name"] == service_name:
                	schedList.append(el)

	jsonObj = {}
	jsonObj["schedule"] = schedJson

	return json.dumps(jsonObj)


@app.route("/handleSchedule.py", methods = ['GET', 'POST'])
def handle_schedule():
	print "Inizio..."
	data = request.get_json()
	print data

	err = open("/tmp/err.out", "w")
	original_stderr = sys.stderr
	sys.stderr = err 

	result = "Error"

	schedule_command = data["schedule_command"]
	device_name = data["device_name"]
	service_name = data["service_name"]
	command = data["command"]

	if "argument" in data.keys():
	        argument = data["argument"]
	else:
        	argument = ""

	if "frequency" in data.keys():
        	frequency = str(data["frequency"])
		print "Frequency schedule - " + frequency
        	su(schedule_command, device_name, service_name, command, argument, "F", frequency)

	elif "time" in data.keys():
		sched_time = data["time"]
		print "Should add schedule at " + sched_time + "!"
        	su(schedule_command, device_name, service_name, command, argument, "T", sched_time)

	else:
        	frequency = ""
		schedId = data["id"]
        	#su(schedule_command, device_name, service_name, command, '', '', '')
        	su(schedule_command, '', '', '', schedId, '', '')

	jsonObject = {
        	"result": "Ok"
	}

	return json.dumps(jsonObject)


@app.route("/handleTrigger.py", methods = ['GET', 'POST'])
def handle_trigger():
	data = request.get_json()
	print data

	
	err = open("/tmp/err.out", "w")
	original_stderr = sys.stderr
	sys.stderr = err

	request_type = data["request"]

	# Reply with available commands
	if request_type == "commands":
        	filename = "devs.json"
        	with open(filename) as data_file:
                	devs = json.load(data_file)

		jsonObj = {}
		jsonObj["commands"] = devs

       		return json.dumps(jsonObj)


	# Reply with active triggers
	if request_type == "triggers":
		trigs = rtff()		
		
		jsonObj = {}
		jsonObj["triggers"] = trigs

        	return json.dumps(jsonObj)


	# Add trigger event
	elif request_type == 'A':
		print "Adding..."
        	
		trigs = rtff()		

		print trigs
			
		print "Conditions"
		print data["conditions"]

        	# Fields: type, device_name, service_name, command, mail_address, gcm_id 
        	then = json.loads(data["then"])
		print then

		trigEl = {}
        	trigEl["then"] = then
		trigEl["conditions"] = data["conditions"] 
        	trigEl["id"] = len(trigs) + 1

        	trigs.append(trigEl)
		print trigs

		wttf(trigs)

        	return json.dumps(then)

	# Remove trigger event
	elif request_type == 'R':

		trigs = rtff()		

        	idToRemove = int(data["id"])

        	res = "No"

        	for i, el in enumerate(trigs):
                	if el["id"] == idToRemove:
                        	del trigs[i]
                        	res = "Si"

		wttf(trigs)

		response = {}
        	response["status"] = res
        	return json.dumps(response)


@app.route("/getServiceData.py", methods = ['GET', 'POST'])
def get_service_data():
	err = open("/tmp/err.out", "w")
	original_stderr = sys.stderr
	sys.stderr = err 

	data = request.get_json()

	device_name = data["device_name"]
	service_name = data["service_name"]
	startMillis = data["start_time"]
	endMillis = data["end_time"] 
	
	start_date = datetime.datetime.fromtimestamp(long(startMillis)/1000).strftime("%Y-%m-%d %H:%M")
	end_date = datetime.datetime.fromtimestamp(long(endMillis)/1000).strftime("%Y-%m-%d %H:%M")

	#filename = "service_data.json"
	#with open(filename) as data_file:
    	#	service_data = json.load(data_file)

	service_data = rsd()

	values = []

	for el in service_data:
        	if el["device_name"] == device_name and el["service_name"] == service_name:
                	values = el["values"]

	values = sorted(values, key=lambda k: k['timestamp'])

	filtered_data = []

	for el in values:
        	if long(el['timestamp']) >= long(startMillis) and long(el['timestamp']) <= long(endMillis):
                	filtered_data.append(el)

	for el in filtered_data:
        	#el["timestamp"] = datetime.datetime.fromtimestamp(long(el["timestamp"])/1000).strftime("%Y-%m-%d %H:%M")
		el["timestamp"] = long(el["timestamp"])	

	jo = {
	        "status" : "Ok",
        	"service_name": service_name,
	        "device_name": device_name,
        	"start_date" : startMillis,
	        "end_date" : end_date,
        	"values": filtered_data
	}

	# Return Json #
	return json.dumps(jo)


@app.route("/setThingSpeak.py", methods = ['POST'])
def set_thingspeak():
	print "---Set ThingSpeak---"

	print request
	data = request.get_json()
	
	print data

	devName = str(data["device_name"])
	servName = str(data["service_name"])
	command = str(data["command"])

	print devName + " " + servName + " " + command

	res = tse(devName, servName, command)

	print res
	
	jsonCurrent = {}

	if command == "GET":
		print "Outside Get"
		if res == True:
			jsonCurrent["result"] = "ON"
		else:
			jsonCurrent["result"] = "OFF"
	
	else:
		if res == 1:
			jsonCurrent["result"] = command

		else:
			jsonCurrent["result"] = False


	return json.dumps(jsonCurrent)


@app.route("/removeDevice.py", methods = ['POST'])
def remove_device():
	print "---Remove Device---"

	data = request.get_json()
	devName = str(data["device_name"])

	res = rd(devName)
		
	jsonCurrent = {}
	jsonCurrent["result"] = res

	return json.dumps(jsonCurrent)
	

def startFlaskServer(f1, f2, f3, f4, f5, f6, f7, f8, f9):
	global ecfp, su, tse, rdff, rsd, rd, rtff, wttf, rsff
	
	ecfp = f1
	su = f2
	tse = f3
	rdff = f4
	rsd = f5
	rd = f6
	rtff = f7
	wttf = f8
	rsff = f9
	
	app.run(host='0.0.0.0', port=5555, debug=True, use_reloader=False, threaded=True)
