#!/usr/bin/python

from routexClient import RoutexClient

rc = RoutexClient()

b = False
while not b:
	b = rc.registerClient("TestProcess")

rc.registerService("Battery", RoutexClient.NUMBER)
rc.addCommandToService("Double", RoutexClient.PARAM)
rc.doneService()

while True:
	if rc.checkServiceRequest():
		servName = rc.getRequestedServiceName()
		comName = rc.getRequestedServiceCommand()
		
		print "Main: " + servName 
		print "Main: " + comName 

		if servName == "Battery":
			if comName == "Get":
				print "Reply"
				rc.serviceResponse("53")	
				print "Sent"

			if comName == "Double":
				arg_str = rc.getRequestedServiceArgument()
				arg_n = int(arg_str)
				print arg_n
				rc.serviceResponse(str(arg_n*2))
