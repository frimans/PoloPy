import asyncio
from dataclasses import dataclass
from functools import cached_property
import sys
import pyqtgraph as pg
import numpy as np

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import qasync

from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

UART_SAFE_SIZE = 20


@dataclass
class QBleakClient(QObject):

    device: BLEDevice

    messageChanged = pyqtSignal(bytes)
    ecg_updated = pyqtSignal(list)

    def data_conv(self, sender, data):
        print("Data recieved")

        if data[0] == 0x00:
            timestamp = self.convert_to_unsigned_long(data, 1, 8)
            step = 3
            samples = data[10:]
            offset = 0
            while offset < len(samples):
                ecg = self.convert_array_to_signed_int(samples, offset, step)
                offset += step

                self.ECG_data.append(ecg)
                if len(self.ECG_data) >1200:
                    self.ECG_data = self.ECG_data[-1200:]

                self.ecg_updated.emit(self.ECG_data)




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
        await self.client.is_connected()

        PMD_CONTROL = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of stream settings ##
        ECG_WRITE = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])
        await self.client.write_gatt_char(PMD_CONTROL, ECG_WRITE)


        PMD_DATA = "FB005C82-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of start stream ##
        await self.client.start_notify(PMD_DATA, self.data_conv)

    async def stop(self):
        await self.client.disconnect()

    async def write(self, data):
        PMD_CONTROL = "FB005C81-02E7-F387-1CAD-8ACD2D8DF0C8"  ## UUID for Request of stream settings ##
        ECG_WRITE = bytearray([0x02, 0x00, 0x00, 0x01, 0x82, 0x00, 0x01, 0x01, 0x0E, 0x00])
        await self.client.write_gatt_char(PMD_CONTROL, ECG_WRITE)


    def _handle_disconnect(self) -> None:
        print("Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()





class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(640, 480)

        self._client = None


        scan_button = QPushButton("Scan Devices")
        self.devices_combobox = QComboBox()
        connect_button = QPushButton("Connect")
        self.message_lineedit = QLineEdit()
        send_button = QPushButton("Send Message")
        self.log_edit = QPlainTextEdit()


        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        lay = QVBoxLayout(central_widget)
        lay.addWidget(scan_button)
        lay.addWidget(self.devices_combobox)
        lay.addWidget(connect_button)
        lay.addWidget(self.message_lineedit)
        lay.addWidget(send_button)
        lay.addWidget(self.log_edit)
        self.plot = pg.plot()


        self.line = self.plot.plot(pen=pg.mkPen(color=(255, 0, 0), width=4))


        scan_button.clicked.connect(self.handle_scan)
        connect_button.clicked.connect(self.handle_connect)
        send_button.clicked.connect(self.handle_send)

    @cached_property
    def devices(self):
        return list()

    @property
    def current_client(self):
        return self._client

    async def build_client(self, device):
        if self._client is not None:
            await self._client.stop()
        self._client = QBleakClient(device)
        self._client.ecg_updated.connect(self.on_ecg_updated)
        self._client.messageChanged.connect(self.handle_message_changed)
        await self._client.start()

    @qasync.asyncSlot()
    async def handle_connect(self):
        self.log_edit.appendPlainText("try connect")
        device = self.devices_combobox.currentData()
        if isinstance(device, BLEDevice):
            await self.build_client(device)
            self.log_edit.appendPlainText("connected")

    @qasync.asyncSlot()
    async def handle_scan(self):
        self.log_edit.appendPlainText("Started scanner")
        self.devices.clear()
        devices = await BleakScanner.discover()
        self.devices.extend(devices)
        self.devices_combobox.clear()
        for i, device in enumerate(self.devices):
            self.devices_combobox.insertItem(i, device.name, device)
        self.log_edit.appendPlainText("Finish scanner")

    def handle_message_changed(self, message):
        self.log_edit.appendPlainText(f"msg: {message.decode()}")
    def on_ecg_updated(self, output):


        self.line.setData( y=output)

    @qasync.asyncSlot()
    async def handle_send(self):
        if self.current_client is None:
            return
        message = self.message_lineedit.text()
        if message:
            await self.current_client.write(message.encode())


def main():
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    w = MainWindow()
    w.show()
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()