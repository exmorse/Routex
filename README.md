# Routex
Routex allows the development of Internet of Things applications.  
It uses a Raspberry Pi as a multi-technology router to create a network 
in which devices using different protocol can interoperate. The behaviour of the 
system is set via Android application or web site.

## Supported Technologies
* WiFi
* Bluetooth
* Zigbee
* nRF24L01
* 433MHz Radio

## Requirements
The following Python modules are required dependencies:
- ```flask``` (https://github.com/pallets/flask)
- ```flask_cors``` (https://github.com/corydolphin/flask-cors)
- ```pigpio``` (https://github.com/joan2937/pigpio)
- ```piVirtualWire``` (https://github.com/DzikuVx/piVirtualWire)
- ```pyRadioHeadNRF24``` (https://github.com/exmorse/pyRadioHeadNRF24)
- ```python-xbee``` (https://github.com/nioinnovation/python-xbee)
- ```pybluez``` (https://github.com/karulis/pybluez)
- ```schedule``` (https://github.com/dbader/schedule)
- ```stopit``` (https://github.com/glenfant/stopit)
- ```python-gcm``` (https://github.com/geeknam/python-gcm)

## Devices
#### Arduino & ESP8266
`ArduinoRoutex.zip` and `ESPRoutex.zip` contain the library to program Arduino and ESP8266
as Routex devices.

#### Bluetooth Android Client
The Bluetooth client app is available in `BluetoothRoutexClient.tar.gz`.

#### Python Program
The Python module `routexClient.py` allows to use a process (running on the Raspberry Pi 
or any other computer) as a device.

## Router
Run `routex.py` with root privileges, with the technologies to be used as argument.  
For example:  `sudo ./routex.py wifi bluetooth zigbee nrf24 rf433`

## Controller 
The controller can be either the Android application (`RoutexControllerApp.tar.gz`) or the 
web site (`RoutexControllerSite`).
