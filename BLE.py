"""
BLE communication with the sensors is implemented in this file.
- Searching for devices
- Connecting to devices
- Use of Bluetooth GATT for data logging and sending for further processing

Author: Severi Friman, severi.friman@gmail.com
"""

# Todo: Serching and communication functions
import PyQt5
from PyQt5.QtBluetooth import QBluetoothDeviceDiscoveryAgent, QLowEnergyController, QBluetoothDeviceInfo, QBluetoothUuid, QLowEnergyService
from PyQt5.QtCore import QObject, pyqtSignal

import asyncio
from math import ceil


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
        """
        print("##### Found devices #####")
        
        for device in self.scanner.discoveredDevices():
            print('Name: {name}, Address: {address} UUID: {UUID}, rssi: {rssi}'.format(UUID=device.deviceUuid().toString(),
                                                                    name=device.name(),
                                                                    rssi=device.rssi(), address = device.address().toString()))
        print("#########################")
        """
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
        print("Forming connection to:", sensor.name(), "Address:", sensor.address().toString())
        if self.controller:
            print("Connection already formed to other sensor.")
            return
        self.controller = QLowEnergyController.createCentral(sensor) # Create the central role placeholder for the device
        print(self.controller.state()) # When not connected the state should be 0
        self.controller.connectToDevice() # Connect to the device
        print(self.controller.state()) # When connected the state should be 2

        """
        Controller states:
        0 = UnconnectedState | The controller is not connected to a remote device.
        1 = ConnectingStage | The controller is attempting to connect to a remote device.
        2 = ConnectedState | The controller is connected to a remote device.
        3 = DiscoveringState | The controller is retrieving the list of services offered by the remote device.
        4 = DiscoveredState | The controller has discovered all services offered by the remote device.
        5 = ClosingState | The controller is about to be disconnected from the remote device.
        6 = AdvertisingState | The controller is currently advertising data.
        """

        self.controller.error.connect(self.error) # In case of error, handle it
        print("contoller created")
        self.controller.discoverServices() # Discover the available services provided by the remote device.
        print("Discovery finished")
        #self.controller.connected.connect(self.find_services)
        self.controller.discoveryFinished.connect(self.choose_services)

    def error(self, err):
        print(err)
    def find_services(self):
        print("Discovering services")


    def choose_services(self):
        print("Found services:")

        """
        Some service UUIDs:
        DeviceInformation = 0x180a | Manufacturer / vendor info about the device.
        HeartRate = 0x180d | Heart rate and other related data.
        
        PhoneAlertStatus = 0x180e | Exposes the phone alert status when connected.
        Battery = 0x180f | Exposes the device battery status.
        UserData = 0x181c | Provides the user related data.
        
        PolarH10 services:
        5c80
        HR_measurement = 2a37
        HR_service = 180d
        Body_sensor_location = 2a38
        Battery_level_characteristic = 2a19
        PSD_service = 5c20
        PFC_service = ff4b | Poler Features Configuration Service
        """
        GATT_service = ['180a','180c', '180d', '180e', '180f']
        for service in self.controller.services():
            UUID = service.toString().replace("{", "").replace("}","")
            print(UUID)
            UUID_parts = UUID.split("-", 4)
            if '180d' in UUID_parts[0]:
                # This is HR_service
                service_to_use = service
        self.HR_service(service_to_use)




    def HR_service(self, hr_service):

        self.hr_service = self.controller.createServiceObject(hr_service)
        self.hr_service.stateChanged.connect(self._start_hr_notification)
        self.hr_service.characteristicChanged.connect(self._data_handler)
        self.hr_service.discoverDetails()

    # For now these two copied from openhrv
    def _start_hr_notification(self, state):
        if state != QLowEnergyService.ServiceDiscovered:
            return
        hr_char = self.hr_service.characteristic(self.HR_CHARACTERISTIC)
        if not hr_char.isValid():
            print(f"Couldn't find HR characterictic on {self._sensor_address()}.")
        self.hr_notification = hr_char.descriptor(
            QBluetoothUuid.DescriptorType.ClientCharacteristicConfiguration
        )
        if not self.hr_notification.isValid():
            print("HR characteristic is invalid.")
        self.hr_service.writeDescriptor(self.hr_notification, self.ENABLE_NOTIFICATION)

    def _data_handler(self, _, data):  # _ is unused but mandatory argument
        """
        `data` is formatted according to the
        "GATT Characteristic and Object Type 0x2A37 Heart Rate Measurement"
        which is one of the three characteristics included in the
        "GATT Service 0x180D Heart Rate".

        `data` can include the following bytes:
        - flags
            Always present.
            - bit 0: HR format (uint8 vs. uint16)
            - bit 1, 2: sensor contact status
            - bit 3: energy expenditure status
            - bit 4: RR interval status
        - HR
            Encoded by one or two bytes depending on flags/bit0. One byte is
            always present (uint8). Two bytes (uint16) are necessary to
            represent HR > 255.
        - energy expenditure
            Encoded by 2 bytes. Only present if flags/bit3.
        - inter-beat-intervals (IBIs)
            One IBI is encoded by 2 consecutive bytes. Up to 18 bytes depending
            on presence of uint16 HR format and energy expenditure.
        """
        data = data.data()  # convert from QByteArray to Python bytes

        byte0 = data[0]
        uint8_format = (byte0 & 1) == 0
        energy_expenditure = ((byte0 >> 3) & 1) == 1
        rr_interval = ((byte0 >> 4) & 1) == 1

        if not rr_interval:
            return

        first_rr_byte = 2
        if uint8_format:
            # hr = data[1]
            pass
        else:
            # hr = (data[2] << 8) | data[1] # uint16
            first_rr_byte += 1
        if energy_expenditure:
            # ee = (data[first_rr_byte + 1] << 8) | data[first_rr_byte]
            first_rr_byte += 2

        for i in range(first_rr_byte, len(data), 2):
            ibi = (data[i + 1] << 8) | data[i]
            # Polar H7, H9, and H10 record IBIs in 1/1024 seconds format.
            # Convert 1/1024 sec format to milliseconds.
            # TODO: move conversion to model and only convert if sensor doesn't
            # transmit data in milliseconds.
            ibi = ceil(ibi / 1024 * 1000)
            self.ibi_update.emit(ibi)




















