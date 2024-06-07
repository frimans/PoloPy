import asyncio
from functools import cached_property
import sys
import pyqtgraph as pg
import numpy as np
from PyQt5 import QtGui
from PyQt5.QtGui import QPixmap
from scipy.fft import fft

from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QGridLayout,
    QProgressBar,
    QWidget, QLabel,
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
        self.HR_data = []
        self.IBI_data = []
        self.ECG_data_save = []
        self.respiratory_rate = []
        self.acc_x = []
        self.acc_y = []
        self.acc_z = []
        self.ACC_calc = np.array(0)
        self.battery_level = 100
        self.update_index = 0
        super().__init__()
        self.resize(800, 400)
        self.pixmap_H10 = QPixmap('Images/H10_icon.png')
        self.pixmap_OH1 = QPixmap('Images/OH1_icon.png')
        self.pixmap_battery = QPixmap('Images/battery_icon.png')

        self._client = None

        self.setWindowTitle("PoloPy")
        self.setWindowIcon(QtGui.QIcon('Images/polopylogo.ico'))
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

        # The real time Graph with pyqtgraph
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
        self.line_HR = self.plot.plot(pen=pen, width=4)

        self.Device_icon = QLabel(self.log_edit)
        self.Device_icon.setScaledContents(True)
        self.Device_icon.setVisible(False)
        self.Device_icon.setGeometry(220, 1, 80, 80)

        self.Battery_icon = QLabel(self.progressbar)
        self.Battery_icon.setPixmap(self.pixmap_battery)
        self.Battery_icon.setScaledContents(True)
        self.Battery_icon.setVisible(False)
        self.Battery_icon.setGeometry(230, 1, 50, 20)

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
        # Connect the updates on the bleak client with the GUI
        # These are the loops for processing the incoming data from the sensor for processing
        self._client = BleakClient.QBleakClient(device)
        self._client.ecg_updated.connect(self.on_ecg_updated)
        self._client.acc_updated.connect(self.on_acc_updated)
        self._client.HR_updated.connect(self.on_HR_updated)
        self._client.Battery_level_read.connect(self.battery_level_updated)

        await self._client.start()
        await self._client.start_HR()
        await self._client.start_ECG()
        await self._client.start_ACC()

    @qasync.asyncSlot()
    async def handle_connect(self):
        self.log_edit.appendPlainText("Connecting...")
        device = self.devices_combobox.currentData()


        if isinstance(device, BLEDevice):
            await self.build_client(device)
            if "H10" in device.name:
                self.Device_icon.setVisible(True)
                self.Device_icon.setPixmap(self.pixmap_H10)
            if "OH1" in device.name:
                self.Device_icon.setVisible(True)
                self.Device_icon.setPixmap(self.pixmap_OH1)
            self.log_edit.clear()

            self.Battery_icon.setVisible(True)

            self.log_edit.appendPlainText("connected to " + str(device.name))
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
            """
                # Calculating measures fromt the raw ECG with heartpy library
                working_data, measures = hp.process(np.array(self.ECG_data), 130)


                if self.update_index == 300:
                    # Update the readings to the plot


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
            """
            self.update_plot()
    def on_acc_updated(self, output):
        # Accelerometer packet received
        for reading in output:
            self.acc_x.append(reading[0])
            self.acc_y.append(reading[1])
            self.acc_z.append(reading[2])
        if len(self.acc_z) >= 4200:
            self.acc_z = self.acc_z[-4200:]
            self.ACC_calc = np.array(self.acc_z) - np.mean(self.acc_z)



            padding = 15000
            hamm1 = np.hamming(len(self.acc_z))
            freq_axis = np.arange(0, 100, 100 / (padding / 2))
            #freq_axis = np.arange(0, 100, 100 / 2200)
            Frequencies = np.abs(fft(self.ACC_calc*hamm1, n = padding))
            Frequencies = Frequencies[0:len(Frequencies) // 2]
            Frequencies = Frequencies / np.max(Frequencies)
            resp = freq_axis[np.argmax(Frequencies)] * 60
            self.respiratory_rate.append(resp)
            self.text_label_resp.setText("Respiratory rate: " + str(np.round(resp, 1)) + " BPM")
            print("Respiration:", resp,"|", np.argmax(Frequencies),"|", freq_axis[np.argmax(Frequencies)])







    def on_HR_updated(self, output):
        # output[0] = Polar HR
        # output[1] = IBI list

        # Here the HR estimate from the device is displayed in the GUI
        self.text_label_HR.setText("Heart rate: " + str(output[0]) + " BPM")
        print("HR: ", output[0])

        # Alternatively the HR can be calculated from the IBI values
        """
        self.IBI_data.append(output[0])
        
        if len(self.IBI_data)> 10:
            HR = (1/(np.average(self.IBI_data[-9:])/1000))*60
            self.text_label_HR.setText("Heart rate: " + str(np.round(output, 1)) + " BPM")

            self.HR_data.append(HR)
            print("HR:", HR)
            #self.update_plot()
        """

        # HRV calculation
        for reading in output[1]:
            self.IBI_data.append(reading)


        RMSSD = np.round(np.sqrt(np.mean(np.square(np.diff(self.IBI_data)))),1)

        self.text_label_HRV.setText("RMSSD: " + str(RMSSD) + " ms")
        print("RMSSD: ", RMSSD, " ms")

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