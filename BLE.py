"""
BLE communication with the sensors is implemented in this file.
- Searching for devices
- Connecting to devices
- Use of Bluetooth GATT for data logging and sending for further processing

Author: Severi Friman, severi.friman@gmail.com
"""

# Todo: Serching and communication functions
import PyQt5
from PyQt5.QtBluetooth import QBluetoothDeviceDiscoveryAgent
from PyQt5.QtCore import QObject

import asyncio
from bleak import BleakScanner

class device_scanner(QObject):
    def __init__(self, timeout):
        super().__init__()
        self.devices = []
        self.scanner = QBluetoothDeviceDiscoveryAgent() # Initialize the scanner
        self.scanner.setLowEnergyDiscoveryTimeout(timeout) # When initializing the device scanner, the timeout time for scanning has to be defined.
        self.scanner.deviceDiscovered.connect(self.discovery)
        self.scanner.finished.connect(self.Use_scan_result) # After scanning timeout, do this
        self.scanner.error.connect(self.Error)

    def Use_scan_result(self):
        """
        After the device scanner has found the
        :return:
        """
        print("Found devices:")
        print(self.scanner.discoveredDevices())
        for device in self.scanner.discoveredDevices():
            print('UUID: {UUID}, Name: {name}, rssi: {rssi}'.format(UUID=device.deviceUuid().toString(),
                                                                    name=device.name(),
                                                                    rssi=device.rssi()))
    def discovery(self,device):
        print("Device found:")
        print(device)

    def Scan_devices(self):
        print("Scanning devices...")
        self.scanner.start()

    def Error(self, err):
        print(err)












