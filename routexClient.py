from socket import *
import time 
import select

	
class RoutexClient:

	STATUS = 'S'
	NUMBER= 'N'
	TEXT = 'T'

	NO_PARAM = 'B'
	PARAM = 'I'

	def __init__(self):
		self.routexAddress = ''
		self.routexPort = 5100
		self.clientPort = 6000
		self.deviceName = ''
		self.sock = None

		self.lastCommand = ''
		self.lastService = ''
		self.lastArgument = ''
		
		self.acceptSock = socket(AF_INET, SOCK_STREAM)
		self.acceptSock.bind(('', 5000))
		self.acceptSock.listen(3)

	def setRoutexAddress(self, address):
		self.routexAddress = address

	def setRoutexPort(self, port):
		self.routexPort = port

	def setClientPort(self, port):
		self.clientPort = port

	def sendMessage(self, message):
		if self.sock == None:
			self.sock = socket(AF_INET, SOCK_STREAM)
			self.sock.bind(('', 0))
			self.sock.connect((self.routexAddress, self.routexPort))
		
		self.sock.send(message)
		return True

	def receiveResponse(self):
		if self.sock == None:
			print "Socket is None"
			return False
	
		read_list = [self.sock]
		readable, writable, errored = select.select(read_list, [], [], 2)
		for sock in readable:
				msg = sock.recv(50)		
				if msg[-1] == '\n':
					return msg[0:(len(msg)-1)]
				else:
					return msg
		return None

	def registerClient(self, name):
		if name == None or name == '':
			print "--- Registered Failed - No Name"
			return False
		
		self.deviceName = name
		self.sendMessage("J!" + self.deviceName + "!A")
		ack = self.receiveResponse()
		
		if ack == None:
			print "Failed"
			return False

		if ack == "J!Ok":
			print "Registered Successfully"

			self.sock.close()
			self.sock = None
			
			return True

	def registerService(self, name, serviceType):	
		if name == None or name == '':
			return False
		
		self.sendMessage("S!A!" + serviceType + "!" + name)
		ack = self.receiveResponse()	
		
		#print ack

		if ack == None:
			print "Failed"
			return False

		if ack == "S!G!Ok":
			print "Service declared successfully"
			return True

	def addCommandToService(self, name, commandType):
		self.sendMessage("S!" + commandType + "!" + name)
		ack = self.receiveResponse()

		#print ack

		if ack == None:
			print "Failed"
			return False

		if ack == "C!Added":
			print "Command added successfully"
			return True

	def doneService(self):
		self.sendMessage("S!DONE")
		ack = self.receiveResponse()	
		
		#print ack

		if ack == None:
			print "Failed"
			return False

		if ack == "S!DONE!Ok":
			print "Service registered successfully"
			return True

	def checkServiceRequest(self):
		read_list = [self.acceptSock]
                readable, writable, errored = select.select(read_list, [], [], 1)
                for sock in readable:
                        #print "---Accepting"
                        self.sock, (dev_address, dev_port) = sock.accept()
                        #print "---Receiving input from : " + str(dev_address) + str(dev_port)
     
                        ready = select.select([self.sock], [], [], 4)
                        if ready[0]:
                                msg = self.sock.recv(200)
				if msg[-1] == '\n':
					msg =  msg[0:(len(msg)-1)]
				
				l = len(msg)
				#print "Received: " + msg

				separatorIndex = msg.find('!')

				if separatorIndex == -1:
					print "Bad Format Request"
					return False

				self.lastService = msg[0:separatorIndex]

				if msg[-1] == '*':
					self.lastCommand = msg[separatorIndex+1:len(msg)-1]
                
					readable, writable, errored = select.select(read_list, [], [], 1)
                			for sock in readable:
                        			self.sock, (dev_address, dev_port) = sock.accept()
                        			argready = select.select([self.sock], [], [], 4)
                        			if argready[0]:
                                			msg = self.sock.recv(50)
							if msg[-1] == '\n':
								msg =  msg[0:(len(msg)-1)]
							if msg[0] != '*':
								return False

							self.lastArgument = msg[2:]
					
				else:
					self.lastCommand = msg[separatorIndex+1:]	

				return True

		return False

	def serviceResponse(self, response):
		self.sendMessage("R!" + response)	
		self.sock.close()
		self.sock = None

	def getRequestedServiceName(self):
		return self.lastService	
		
	def getRequestedServiceCommand(self):
		return self.lastCommand	
		
	def getRequestedServiceArgument(self):
		return self.lastArgument	
