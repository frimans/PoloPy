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
        print("The scanning has ended!!!")
        for dev in devices:
            print(dev.name())
            print(dev.address().toString())

        self.scanner = sc()
        self.scanner.connect(devices[1])




def main():
    app = Application(sys.argv)
    #app.GUI.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

