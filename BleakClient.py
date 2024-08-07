
import asyncio
import struct

import numpy as np
import time
import math
from dataclasses import dataclass
from functools import cached_property
from PyQt5.QtCore import QObject, pyqtSignal
from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak import BleakScanner
import qasync


@dataclass
class QBleakClient(QObject):
    device: BLEDevice
    ecg_updated = pyqtSignal(int)
    ppg_updated = pyqtSignal(list)
    acc_updated = pyqtSignal(list)
    HR_updated = pyqtSignal(list)
    Battery_level_read = pyqtSignal(int)
    first_acc_record = True


    def ecg_data_conv(self, sender, data):
        if data[0] == 0x00:
            #timestamp = self.convert_to_unsigned_long(data, 1, 8)
            step = 3
            samples = data[10:]
            offset = 0
            ecg_package = []
            while offset < len(samples):
                ecg = self.convert_array_to_signed_int(samples, offset, step)
                offset += step
                ecg_package.append(ecg)
                self.ecg_updated.emit(ecg)
    def ppg_data_conv(self, sender, data):
        # type1 (8)
        # timestamp (64)
        # type2 (8)
        # list of sample, where each is:
        #   ppg1 (24)
        #   ppg2 (24)
        #   ppg3 (24)
        #   amb (24)



        def get_ppg_value(subdata):

            # A bit of magic happening here with the padding.
            # Since the value comes as a 24 bit signed int, it's padded to allow the use
            # of struct.unpack("<i") since that takes a 32 bit signed integer.
            # The padding is then either 0xFF or 0x00 depending of if the most significant
            # bit of the most significant byte of the 24 bit value was set. Since this
            # determine if the value was positive of negative.
            return struct.unpack("<i", subdata + (b'\0' if subdata[2] < 128 else b'\xff'))[0]


        numSamples = math.floor((len(data) - 10) / 12)
        for x in range(numSamples):
            channel_samples = []
            for y in range(4):
                channel_samples.append(get_ppg_value(data[10 + x * 12 + y * 3:(10 + x * 12 + y * 3) + 3]))


            self.ppg_updated.emit(channel_samples)


    def hr_data_conv(self, sender, data):
        """
        `data` is formatted according to the GATT Characteristic and Object Type 0x2A37 Heart Rate Measurement which is one of the three characteristics included in the "GATT Service 0x180D Heart Rate".
        `data` can include the following bytes:
        - flags
            Always present.
            - bit 0: HR format (uint8 vs. uint16)
            - bit 1, 2: sensor contact status
            - bit 3: energy expenditure status
            - bit 4: RR interval status
        - HR
            Encoded by one or two bytes depending on flags/bit0. One byte is always present (uint8). Two bytes (uint16) are necessary to represent HR > 255.
        - energy expenditure
            Encoded by 2 bytes. Only present if flags/bit3.
        - inter-beat-intervals (IBIs)
            One IBI is encoded by 2 consecutive bytes. Up to 18 bytes depending on presence of uint16 HR format and energy expenditure.
        """
        byte0 = data[0]  # heart rate format
        uint8_format = (byte0 & 1) == 0
        energy_expenditure = ((byte0 >> 3) & 1) == 1
        rr_interval = ((byte0 >> 4) & 1) == 1

        if not rr_interval:
            return

        first_rr_byte = 2
        if uint8_format:
            hr = data[1]
            pass
        else:
            hr = (data[2] << 8) | data[1]  # uint16
            first_rr_byte += 1

        if energy_expenditure:
            # ee = (data[first_rr_byte + 1] << 8) | data[first_rr_byte]
            first_rr_byte += 2
        values = []
        for i in range(first_rr_byte, len(data), 2):
            ibi = (data[i + 1] << 8) | data[i]
            # Polar H7, H9, and H10 record IBIs in 1/1024 seconds format.
            # Convert 1/1024 sec format to milliseconds.

            # transmit data in milliseconds.
            ibi = np.ceil(ibi / 1024 * 1000)
            values.append(ibi)
            #self.ibi_queue_values.enqueue(np.array([ibi]))
            #self.ibi_queue_times.enqueue(np.array([time.time_ns() / 1.0e9]))
        self.HR_updated.emit([hr, values])

    def acc_data_conv(self, sender, data):
        # [02 EA 54 A2 42 8B 45 52 08 01 45 FF E4 FF B5 03 45 FF E4 FF B8 03 ...]
        # 02=ACC,
        # EA 54 A2 42 8B 45 52 08 = last sample timestamp in nanoseconds,
        # 01 = ACC frameType,
        # sample0 = [45 FF E4 FF B5 03] x-axis(45 FF=-184 millig) y-axis(E4 FF=-28 millig) z-axis(B5 03=949 millig) ,
        # sample1, sample2,

        if data[0] == 0x02:
            time_step = 0.005  # 200 Hz sample rate
            timestamp = self.convert_to_unsigned_long(data, 1,
                                                          8) / 1.0e9  # timestamp of the last sample in the record

            frame_type = data[9]
            resolution = (frame_type + 1) * 8  # 16 bit
            step = math.ceil(resolution / 8.0)
            samples = data[10:]
            n_samples = math.floor(len(samples) / (step * 3))
            record_duration = (n_samples - 1) * time_step  # duration of the current record received in seconds

            if self.first_acc_record:  # First record at the start of the stream
                stream_start_t_epoch_s = time.time_ns() / 1.0e9 - record_duration
                stream_start_t_polar_s = timestamp - record_duration
                self.polar_to_epoch_s = stream_start_t_epoch_s - stream_start_t_polar_s
                self.first_acc_record = False

            sample_timestamp = timestamp - record_duration + self.polar_to_epoch_s  # timestamp of the first sample in the record in epoch seconds
            offset = 0
            Acc_list = []
            while offset < len(samples):
                x = self.convert_array_to_signed_int(samples, offset, step) / 100.0
                offset += step
                y = self.convert_array_to_signed_int(samples, offset, step) / 100.0
                offset += step
                z = self.convert_array_to_signed_int(samples, offset, step) / 100.0
                offset += step

                #self.acc_queue_times.enqueue(np.array([sample_timestamp]))
                #self.acc_queue_values.enqueue(np.array([x, y, z]))
                Acc_list.append([x, y, z])

                sample_timestamp += time_step
            self.acc_updated.emit(Acc_list)


    def convert_array_to_signed_int(self, data, offset, length):
        return int.from_bytes(
            bytearray(data[offset: offset + length]), byteorder="little", signed=True,
        )

    def convert_to_unsigned_long(self, data, offset, length):
        return int.from_bytes(
            bytearray(data[offset: offset + length]), byteorder="little", signed=False,
        )

    def __post_init__(self):
        super().__init__()
        self.ECG_data = []

    @cached_property
    def client(self) -> BleakClient:
        return BleakClient(self.device, disconnected_callback=self._handle_disconnect)
    async def scan(self):
        devices = await BleakScanner.discover()
        print(devices)

    async def start(self):
        await self.client.connect()


        ## UUID for battery level ##
        BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

        ## DEVICE INFORMATION SERVICE
        DEVICE_INFORMATION_SERVICE = "0000180a-0000-1000-8000-00805f9b34fb"
        MANUFACTURER_NAME_UUID = "00002a29-0000-1000-8000-00805f9b34fb"
        MODEL_NBR_UUID = "00002a24-0000-1000-8000-00805f9b34fb"
        SERIAL_NUMBER_UUID = "00002a25-0000-1000-8000-00805f9b34fb"
        HARDWARE_REVISION_UUID = "00002a27-0000-1000-8000-00805f9b34fb"
        FIRMWARE_REVISION_UUID = "00002a26-0000-1000-8000-00805f9b34fb"
        SOFTWARE_REVISION_UUID = "00002a28-0000-1000-8000-00805f9b34fb"
        SYSTEM_ID_UUID = "00002a23-0000-1000-8000-00805f9b34fb"

        self.model_number = await self.client.read_gatt_char(MODEL_NBR_UUID)
        self.manufacturer_name = await self.client.read_gatt_char(MANUFACTURER_NAME_UUID)
        self.serial_number = await self.client.read_gatt_char(SERIAL_NUMBER_UUID)
        self.battery_level = await self.client.read_gatt_char(BATTERY_LEVEL_UUID)
        self.firmware_revision = await self.client.read_gatt_char(FIRMWARE_REVISION_UUID)
        self.hardware_revision = await self.client.read_gatt_char(HARDWARE_REVISION_UUID)
        self.software_revision = await self.client.read_gatt_char(SOFTWARE_REVISION_UUID)


        if "OH1" in ''.join(map(chr, self.model_number)):
            print("Optical sensor info")
            print("----------------------")
        elif "H10" in ''.join(map(chr, self.model_number)):
            print("ECG strap sensor info")
            print("----------------------")



        Battery_level = int(self.battery_level[0])
        BLUE = "\033[94m"
        RESET = "\033[0m"
        print(f"Model Number: {BLUE}{''.join(map(chr, self.model_number))}{RESET}\n"
              f"Bluetooth address: {BLUE}{self.device.address}{RESET}\n"
              f"Manufacturer Name: {BLUE}{''.join(map(chr, self.manufacturer_name))}{RESET}\n"
              f"Serial Number: {BLUE}{''.join(map(chr, self.serial_number))}{RESET}\n"
              f"Battery Level: {BLUE}{int(self.battery_level[0])}%{RESET}\n"
              f"Firmware Revision: {BLUE}{''.join(map(chr, self.firmware_revision))}{RESET}\n"
              f"Hardware Revision: {BLUE}{''.join(map(chr, self.hardware_revision))}{RESET}\n"
              f"Software Revision: {BLUE}{''.join(map(chr, self.software_revision))}{RESET}")

        """
        Measurement type:
        ECG = 0,
        PPG = 1,
        ACC = 2,
        PPI = 3,
        GYRO = 5,
        MAG = 6
        """

        # Read the battery level and emit it to the GUI for displaying
        self.Battery_level_read.emit(Battery_level)


    async def start_HR(self):
        HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"
        await self.client.start_notify(HEART_RATE_MEASUREMENT_UUID, self.hr_data_conv)

    async def start_ECG(self):
        PMD_CONTROL = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of stream settings ##
        PMD_DATA = "FB005C82-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of start stream ##
        ECG_WRITE = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])
        await self.client.write_gatt_char(PMD_CONTROL, ECG_WRITE)
        await self.client.start_notify(PMD_DATA, self.ecg_data_conv)

    async def start_ACC(self):
        ACC_WRITE = bytearray([0x02, 0x02, 0x00, 0x01, 0xC8, 0x00, 0x01, 0x01, 0x10, 0x00, 0x02, 0x01, 0x08, 0x00])
        PMD_CONTROL = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of stream settings ##
        PMD_DATA = "FB005C82-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of start stream ##
        await self.client.write_gatt_char(PMD_CONTROL, ACC_WRITE)
        await self.client.start_notify(PMD_DATA, self.acc_data_conv)

    async def start_PPG(self):
        """

        Tell the OH-1 that it should start to stream PPG values

        cmd = []
        cmd.append(PolarDevice.CPOpCode.START_MEASUREMENT.value)
        cmd.append(PolarDevice.MeasurementType.PPG.value)
        cmd.append(0x00)  # Sample rate Setting
        cmd.append(0x01)  # array count (?)
        cmd.append(0x82)  # 16 bit value: 130 Hz
        cmd.append(0x00)  # see above
        cmd.append(0x01)  # Resolution Setting
        cmd.append(0x01)  # array count
        cmd.append(0x16)  # 16 bit value: 22 bit
        cmd.append(0x00)  # see above
        """


        PPG_WRITE = bytearray([0x02, 0x01, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x16, 0x00])
        PMD_CONTROL = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of stream settings ##
        PMD_DATA = "FB005C82-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of start stream ##
        await self.client.write_gatt_char(PMD_CONTROL, PPG_WRITE)
        await self.client.start_notify(PMD_DATA, self.ppg_data_conv)


    async def stop(self):
        await self.client.disconnect()

    def _handle_disconnect(self, true):
        print("Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()