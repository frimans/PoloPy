
import asyncio
from dataclasses import dataclass
from functools import cached_property
from PyQt5.QtCore import QObject, pyqtSignal
from bleak import BleakClient
from bleak.backends.device import BLEDevice

@dataclass
class QBleakClient(QObject):
    device: BLEDevice
    ecg_updated = pyqtSignal(list)
    Battery_level_read = pyqtSignal(int)

    def data_conv(self, sender, data):
        if data[0] == 0x00:
            timestamp = self.convert_to_unsigned_long(data, 1, 8)
            step = 3
            samples = data[10:]
            offset = 0
            ecg_package = []
            while offset < len(samples):
                ecg = self.convert_array_to_signed_int(samples, offset, step)
                offset += step
                ecg_package.append(ecg)
            self.ecg_updated.emit(ecg_package)

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

    async def start(self):
        await self.client.connect()

        ## UUID for battery level ##
        BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

        BL = await self.client.read_gatt_char(BATTERY_LEVEL_UUID)
        Battery_level = int(BL[0])
        print(Battery_level, "%")
        self.Battery_level_read.emit(Battery_level)

        PMD_CONTROL = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of stream settings ##
        ECG_WRITE = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])
        await self.client.write_gatt_char(PMD_CONTROL, ECG_WRITE)

        PMD_DATA = "FB005C82-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of start stream ##
        await self.client.start_notify(PMD_DATA, self.data_conv)

    async def stop(self):
        await self.client.disconnect()

    def _handle_disconnect(self) -> None:
        print("Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()