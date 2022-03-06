import os
from ats.easypy import run


def main():
    testscript = os.path.join('./failure_test_script.py')
    run(testscript=testscript)
