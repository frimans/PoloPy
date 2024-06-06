import BLE

from BLE import device_scanner as ds
from BLE import Sensor_client as sc
from PyQt5.QtWidgets import QMainWindow, QApplication
import sys


class GUI(QMainWindow):
    def __init__(self):
        super().__init__()

class Application(QApplication):
    def __init__(self, sys_argv):

        super(Application, self).__init__(sys_argv)
        self.GUI = GUI()
        self.device_scanner = ds(timeout=5000)
        self.device_scanner.Scan_devices()
        self.device_scanner.scan_ends.connect(self.scanning_ends)
    def scanning_ends(self, devices):
        print("The scanning has ended!!!\n")

        self.scanner = sc()
        Polar_devices = []
        H10_MAC = ''
        H10 = None
        for d in range(0,len(devices)):
            if "Polar" in devices[d].name():
                Polar_devices.append(devices[d])
        print("Found Polar devices:", len(Polar_devices))
        for device in Polar_devices:
            print('----- Name: {name}, Address: {address} UUID: {UUID}, rssi: {rssi}'.format(
                UUID=device.deviceUuid().toString(),
                name=device.name(),
                rssi=device.rssi(), address=device.address().toString()))
            if 'H10' in device.name():

                H10_MAC = device.address().toString()
                self.scanner.connect(device)

def main():
    app = Application(sys.argv)
    #app.GUI.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

