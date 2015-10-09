#!/usr/bin/env python
import rospy
import rosparam
import json
import yaml

from atf_msgs.msg import *
from copy import copy


class ATF:
    def __init__(self, testblocks):

        self.testblocks = testblocks
        self.error = False
        self.error_outside_testblock = False
        self.testblock_error = {}
        self.test_name = rosparam.get_param("/analysing/test_name")
        self.number_of_tests = rosparam.get_param("/number_of_tests")

        self.test_status_publisher = rospy.Publisher("atf/test_status", TestStatus, queue_size=1)

        test_status = TestStatus()
        test_status.test_name = self.test_name
        test_status.status_analysing = 1
        test_status.total = self.number_of_tests

        self.test_status_publisher.publish(test_status)

    def check_states(self):
        running_testblocks = copy(self.testblocks)
        while not rospy.is_shutdown() and not self.error:
            for testblock in self.testblocks:
                try:
                    if testblock.get_state() == Status.ERROR:
                        self.testblock_error[testblock.testblock_name] = Status.ERROR
                        rospy.loginfo("An error occured during analysis in '" + testblock.testblock_name +
                                      "', no useful " + "results available.")
                        self.error = True
                        break
                    elif testblock.get_state() == Status.FINISHED:
                        running_testblocks.remove(testblock)
                except ValueError:
                    pass
            if len(running_testblocks) == 0:
                break

        if rospy.is_shutdown():
            self.error_outside_testblock = True

        self.export_to_file()

    def export_to_file(self):
        doc = {}
        if self.error_outside_testblock:
            doc["error"] = "An error occured outside monitored testblocks. Aborted analysis..."
        else:
            for item in self.testblocks:
                name = item.testblock_name
                if name in self.testblock_error:
                    doc.update({name: {"status": "error"}})
                else:
                    for metric in item.metrics:
                        result = metric.get_result()
                        if result is not False:
                            (m, data) = result
                            if name not in doc:
                                doc.update({name: {m: data}})
                            else:
                                if m not in doc[name]:
                                    doc[name].update({m: data})
                                else:
                                    doc[name][m].update(data)
                        else:
                            item.exit()
                            break

        test_status = TestStatus()
        test_status.test_name = self.test_name
        test_status.status_analysing = 2
        test_status.total = self.number_of_tests

        self.test_status_publisher.publish(test_status)

        filename = rosparam.get_param("/analysing/result_json_output") + self.test_name + ".json"
        stream = file(filename, 'w')
        json.dump(copy(doc), stream)

        filename = rosparam.get_param("/analysing/result_yaml_output") + self.test_name + ".yaml"
        if not filename == "":
            stream = file(filename, 'w')
            yaml.dump(doc, stream)
