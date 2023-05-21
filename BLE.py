"""
BLE communication with the sensors is implemented in this file.
- Searching for devices
- Connecting to devices
- Use of Bluetooth GATT for data logging and sending for further processing

Author: Severi Friman, severi.friman@gmail.com
"""

# Todo: Serching and communication functions
import PyQt5
from PyQt5.QtBluetooth import QBluetoothDeviceDiscoveryAgent, QLowEnergyController, QBluetoothDeviceInfo
from PyQt5.QtCore import QObject, pyqtSignal

import asyncio
from bleak import BleakScanner

class device_scanner(QObject):
    scan_ends = pyqtSignal(object)
    def __init__(self, timeout):
        super().__init__()
        self.devices = []
        self.finished = False
        self.scanner = QBluetoothDeviceDiscoveryAgent() # Initialize the scanner
        self.scanner.setLowEnergyDiscoveryTimeout(timeout) # When initializing the device scanner, the timeout time for scanning has to be defined.
        self.scanner.deviceDiscovered.connect(self.discovery) # When device found, save and print the information
        self.scanner.finished.connect(self.Use_scan_result) # After scanning timeout, do this
        self.scanner.error.connect(self.Error)

    def Use_scan_result(self):
        """
        After the device scanner has timed out, the devices are listed
        """
        print()
        print("##### Found devices #####")
        for device in self.scanner.discoveredDevices():
            print('Name: {name}, Address: {address} UUID: {UUID}, rssi: {rssi}'.format(UUID=device.deviceUuid().toString(),
                                                                    name=device.name(),
                                                                    rssi=device.rssi(), address = device.address().toString()))
        print("#########################")
        self.finished = True
        self.scan_ends.emit(self.scanner.discoveredDevices())

    def discovery(self, device):
        """
        Every time the device agent finds a device, the information is printed.
        :param device: Qt device object
        :return:
        """
        print("Device found:")
        print("----", device.name())


    def Scan_devices(self):
        """
        Starts the scanning process
        :return:
        """
        print("Scanning devices...")
        self.scanner.start()

    def Error(self, err):
        print(err)

class Sensor_client(QObject):
    def __init__(self):
        super().__init__()
        self.sensor_address = ""
        self.controller = None
    def connect(self, sensor):
        print("Forming connection to:", sensor.name())
        if self.controller:
            print("Connection allready formed to other sensor.")
            return
        self.controller = QLowEnergyController.createCentral(QBluetoothDeviceInfo(sensor))
        self.controller.error.connect(self.error)
        print("contoller created")
        self.controller.connected.connect(self.find_services)
        self.controller.discoveryFinished.connect(self.choose_services())
    def error(self, err):
        print(err)
    def find_services(self):
        print("Discovering services")
        self.controller.discoverServices()

    def choose_services(self):
        for service in self.controller.services():
            print(service)




















