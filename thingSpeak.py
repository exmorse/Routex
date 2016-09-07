import requests

CREATE_CHANNEL_URL = 'https://api.thingspeak.com/channels.json'
UPDATE_URL = 'https://api.thingspeak.com/update.json'

# Should return write key
def createChannel(devName, servName, userKey):

	channel_name = devName + " - " + servName

        params = dict(
                api_key=userKey,
                name=channel_name,
                field1=servName
        )

        resp = requests.post(url=CREATE_CHANNEL_URL, params=params)

        respJson = resp.json()

	for k in respJson["api_keys"]:		
		if k["write_flag"] == True:
			return k["api_key"]

	return False


def addData(channel_key, value):

	print "Add data"

        params = dict(
                api_key=channel_key,
		field1=value
        )

        print params

        resp = requests.post(url=UPDATE_URL, params=params)

        print resp.json()

if __name__ == "__main__":
	print createChannel("Arduino", "Temperatura")
