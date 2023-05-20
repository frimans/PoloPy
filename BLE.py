"""
BLE communication with the sensors is implemented in this file.
- Searching for devices
- Connecting to devices
- Use of Bluetooth GATT for data logging and sending for further processing

Author: Severi Friman, severi.friman@gmail.com
"""

# Todo: Serching and communication functions

from PyQt5.QtBluetooth import QBluetoothDeviceDiscoveryAgent

class device_scanner():
    def __init__(self, timeout):
        self.scanner = QBluetoothDeviceDiscoveryAgent() # Initialize the scanner
        self.scanner.setLowEnergyDiscoveryTimeout(timeout) # When initializing the device scanner, the timeout time for scanning has to be defined.
        self.scanner.finished.connect(self.Use_scan_result) # After scanning timeout, do this

    def Use_scan_result(self):
        """
        After the device scanner has found the
        :return:
        """







