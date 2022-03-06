import logging
import re
import time

from ats import aetest
from ats.log.utils import banner
from genie.conf import Genie
from genie.abstract import Lookup # noqa
from genie.libs import ops # noqa
from pyats.async_ import pcall
from tabulate import tabulate
import yaml


log = logging.getLogger(__name__)

###################################################################
#                  COMMON SETUP SECTION                           #
###################################################################


class common_setup(aetest.CommonSetup):
    """ Common Setup section """

    # Connect to each device in the testbed
    @aetest.subsection
    def connect(self, testbed):
        genie_testbed = Genie.init(testbed)
        self.parent.parameters['testbed'] = genie_testbed
        device_list = []
        for device in genie_testbed.devices.values():
            if device.os in ("ios", "iosxe", "nxos"):
                log.info(banner(
                    "Connect to device '{d}'".format(d=device.name)))
                try:
                    device.connect()
                except Exception:
                    self.failed("Failed to establish connection to '{}'".format(device.name))
                device_list.append(device)

        # Pass list of devices the to testcases
        self.parent.parameters.update(dev=device_list)


###################################################################
#                     TESTCASES SECTION                           #
###################################################################

class failure_test(aetest.Testcase):
    """ This is user Testcases section """

    def execute_ping(self, device, dest, repeat, timeout):
        cmd_timeout = int(repeat) * int(timeout) + 10
        ping_result = device.execute("ping {} repeat {} timeout {}".format(dest, repeat, timeout), timeout=cmd_timeout)
        m = re.search(r'\(([0-9]+)/([0-9]+)\)', ping_result)
        down_time = (int(m.groups(0)[1]) - int(m.groups(0)[0])) * int(timeout)
        return down_time

    def shutdown_interface(self, device, item, delay=1, unconfig=False):
        time.sleep(delay)
        intf = item["target_interface"]
        cmd = 'no ' if unconfig else ''
        if type(intf) is str:
            device.configure("interface {}\n {}shutdown".format(intf, cmd))
        elif type(intf) is list:
            intfs = ', '.join(intf)
            if device.os == 'ios' or device.os == 'iosxe':
                device.configure("interface range {}\n {}shutdown".format(intfs, cmd))
            elif device.os == 'nxos':
                device.configure("interface {}\n {}shutdown".format(intfs, cmd))
        else:
            raise Exception('target_interface {} is not supported'.format(intf))

    @aetest.test
    def count_downtime(self, testbed):
        try:
            with open('test_senario.yaml') as file:
                test_data = yaml.safe_load(file)
        except Exception as e:
            self.failed('Exception occurred while loading YAML...{}'.format(e))

        ping_dev = test_data['ping_device']
        ping_dest = test_data['ping_dest']
        ping_repeat = test_data['ping_repeat']
        ping_timeout = test_data['ping_timeout']
        test_interval = test_data['test_interval']
        test_item = test_data['test_item']

        mega_tabular = []

        for item in test_item:
            shutdown_device = testbed.devices[item["target_device"]]
            ping_device = testbed.devices[ping_dev]

            # If the shutdown device and ping device are the same, execute two functions at the same time
            # to prevent shutdown is executed after ping is completely finished.
            delay = 0 if item["target_device"] == ping_dev else 1

            (_, shut_result) = pcall([self.shutdown_interface, self.execute_ping],
                                     iargs=[[shutdown_device, item, delay], [ping_device, ping_dest, ping_repeat, ping_timeout]])
            log.info(banner("Downtime of {} shutdown: {} sec".format(item, shut_result)))

            time.sleep(test_interval)

            (_, no_shut_result) = pcall([self.shutdown_interface, self.execute_ping],
                                        iargs=[[shutdown_device, item, delay, True], [ping_device, ping_dest, ping_repeat, ping_timeout]])
            log.info(banner("Downtime of {} no shutdown: {} sec".format(item, no_shut_result)))

            time.sleep(test_interval)

            mega_list = [item["target_device"], item["target_interface"], shut_result, no_shut_result]
            mega_tabular.append(mega_list)

        log.info(tabulate(mega_tabular,
                          headers=['Device', 'Interface', 'Shutdown Downtime(sec)', 'No Shutdown Downtime(sec)'],
                          tablefmt='orgtbl'))


class common_cleanup(aetest.CommonCleanup):
    """ Common Cleanup for Sample Test """

    @aetest.subsection
    def clean_everything(self):
        """ Common Cleanup Subsection """
        log.info("All Done! ")


if __name__ == '__main__':
    aetest.main()
