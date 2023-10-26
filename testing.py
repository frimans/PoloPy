import asyncio
from functools import cached_property
import sys
import numpy
import pyqtgraph as pg
import numpy as np
from PyQt5 import QtGui

from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QGridLayout,
    QProgressBar,
    QWidget,
)

import heartpy as hp
import BleakClient

import qasync
from bleak import BleakScanner
from bleak.backends.device import BLEDevice


UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

UART_SAFE_SIZE = 20
Battery_level = 100


class MainWindow(QMainWindow):
    """
    This is a class for the QT based user interface (UI).
    """
    def __init__(self):
        self.streaming = False
        self.ECG_data = []
        self.ECG_data_save = []
        self.battery_level = 100
        self.update_index = 0
        super().__init__()
        self.resize(800, 400)

        self._client = None

        self.setWindowTitle("PoloPy")
        self.setWindowIcon(QtGui.QIcon('polopylogo.ico'))
        scan_button = QPushButton("Scan Devices")
        scan_button.setFixedWidth(300)
        self.devices_combobox = QComboBox()
        self.devices_combobox.setFixedWidth(300)
        connect_button = QPushButton("Connect")
        connect_button.setFixedWidth(300)
        disconnect_button = QPushButton("Disconnect")

        self.log_edit = QPlainTextEdit()
        self.log_edit.setFixedWidth(300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        lay = QGridLayout(central_widget)
        lay.addWidget(scan_button)
        lay.addWidget(self.devices_combobox)
        lay.addWidget(connect_button)
        #lay.addWidget(disconnect_button)
        lay.addWidget(self.log_edit)
        self.progressbar = QProgressBar(self, minimum=0, maximum=100)
        self.progressbar.setFixedWidth(300)

        lay.addWidget(self.progressbar)
        self.progressbar.setStyleSheet(
            "QProgressBar::chunk "
            "{"
            "background-color: green;"
            "}")

        self.plot = pg.PlotWidget()
        self.text_label_HR = pg.LabelItem("Heart Rate: - BPM")
        self.text_label_HR.setParentItem(self.plot.graphicsItem())
        self.text_label_HR.anchor(itemPos=(0.1, 0.06), parentPos=(0.1, 0.06))

        self.text_label_resp = pg.LabelItem("Respiratory rate: - BPM")
        self.text_label_resp.setParentItem(self.plot.graphicsItem())
        self.text_label_resp.anchor(itemPos=(0.1, 0.1), parentPos=(0.1, 0.1))

        self.text_label_HRV = pg.LabelItem("Heart rate variablitiy: - ms")
        self.text_label_HRV.setParentItem(self.plot.graphicsItem())
        self.text_label_HRV.anchor(itemPos=(0.1, 0.14), parentPos=(0.1, 0.14))

        cm = pg.ColorMap([0.0, 1.0], [(255,255,255, 0), 'r'])
        pen = cm.getPen(span=(0, 400), width=5, orientation='horizontal')
        self.line = self.plot.plot(pen=pen, width=4)

        # The Plot widget is scalable
        lay.addWidget(self.plot,0,1, 5, 1)

        scan_button.clicked.connect(self.handle_scan)
        connect_button.clicked.connect(self.handle_connect)
        disconnect_button.clicked.connect(self.stop_client)


    @cached_property
    def devices(self):
        return list()

    @property
    def current_client(self):
        return self._client

    @qasync.asyncSlot()
    async def stop_client(self):
        await self._client.stop()


    async def build_client(self, device):
        if self._client is not None:
            await self._client.stop()
        self._client = BleakClient.QBleakClient(device)
        self._client.ecg_updated.connect(self.on_ecg_updated)
        self._client.Battery_level_read.connect(self.battery_level_updated)

        await self._client.start()

    @qasync.asyncSlot()
    async def handle_connect(self):
        self.log_edit.appendPlainText("Connecting...")
        device = self.devices_combobox.currentData()
        if isinstance(device, BLEDevice):
            await self.build_client(device)
            self.log_edit.appendPlainText("connected")
            self.log_edit.appendPlainText("Device Battery level: " + str(self.battery_level) + " %")

            if self.battery_level < 60:
                self.progressbar.setStyleSheet("QProgressBar::chunk "
                          "{"
                    "background-color: yellow;"
                    "}")
            elif self.battery_level < 30:
                self.progressbar.setStyleSheet(
                    "QProgressBar::chunk "
                    "{"
                    "background-color: red;"
                    "}")
            else:
                self.progressbar.setStyleSheet(
                "QProgressBar::chunk "
                "{"
                "background-color: green;"
                "}")


            self.progressbar.setValue(self.battery_level)
            self.log_edit.appendPlainText("Preparing data stream...")

    @qasync.asyncSlot()
    async def handle_scan(self):
        self.log_edit.appendPlainText("Scanning for Polar devices...")
        self.devices.clear()
        devices = await BleakScanner.discover()
        self.devices.extend(devices)
        self.devices_combobox.clear()
        Polar_amount = 0
        for i, device in enumerate(self.devices):
            if device.name == None:
                pass
            elif "Polar" in device.name:
                Polar_amount +=1

                self.devices_combobox.insertItem(i, device.name, device)
        self.log_edit.appendPlainText("Finished scanning. Found " + str(Polar_amount) + " Polar device(s).")
        if Polar_amount !=0:
            self.log_edit.appendPlainText("Select a device from the list for connecting.")

    def battery_level_updated(self, level):
        self.battery_level = level

    def on_ecg_updated(self, output):
        if len(self.ECG_data) == 0:
            self.streaming == True
            self.log_edit.appendPlainText("Streaming")

        self.ECG_data_save.append(output)
        for i in output:
            self.ECG_data.append(i)

            if len(self.ECG_data) >= 1200:
                self.ECG_data = self.ECG_data[-1200:]

                # Calculating measures fromt the raw ECG with heartpy library
                working_data, measures = hp.process(np.array(self.ECG_data), 130)


                if self.update_index == 300:
                    # Update the readings to the plot
                    if numpy.isnan(measures['bpm'] ):
                        self.text_label_HR.setText("Heart rate: - BPM")
                    else:
                        self.text_label_HR.setText("Heart rate: " + str(int(measures['bpm'])) + " BPM")

                    if numpy.isnan(measures['breathingrate']):
                        self.text_label_resp.setText("Respiratory rate: - BPM")
                    else:
                        self.text_label_resp.setText("Respiratory rate: " + str(int(measures['breathingrate'] * 60)) + " BPM")

                    if numpy.isnan(measures['rmssd']):
                        self.text_label_HRV.setText("RMSSD: - ms")
                    else:
                        self.text_label_HRV.setText("RMSSD: " + str(int(measures['rmssd'])) + " ms")
                    self.update_index = 0

                self.update_index += 1



            self.update_plot()




    def update_plot(self):
        self.line.setData(y=self.ECG_data)



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