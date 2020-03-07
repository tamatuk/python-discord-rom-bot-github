import os
import signal
import sys
import time
import logging

from subprocess import Popen

from discord_server import create_server

COMMANDS = ['start', 'stop', 'restart']


def set_saved_pid(pid):
    f = open("pid.txt", "w")
    f.write(str(pid))


def get_saved_pid():
    try:
        f = open("pid.txt")
        return int(f.read())
    except IOError:
        return 0


def delete_saved_pid():
    try:
        os.remove("pid.txt")
    except OSError:
        pass


def get_started_pid():
    pid = get_saved_pid()
    try:
        os.kill(pid, 0)
    except OSError:
        return 0
    else:
        return pid


def kill_process(pid):
    os.kill(pid, signal.SIGKILL)


def start():
    if not get_started_pid():
        p = Popen([
            'python3', os.path.abspath(__file__),
            'daemon',
        ])
        pid = p.pid
        set_saved_pid(pid)
        logging.info('Server started (pid {}).'.format(pid))
    else:
        logging.info('Server already started.')


def stop():
    pid = get_saved_pid()
    if pid:
        try:
            kill_process(pid)
            logging.info('Server stopped (pid {})'.format(pid))
        except Exception as e:
            logging.error('Server not started (pid {})'.format(pid))
            logging.exception(e)
        delete_saved_pid()
    else:
        logging.info('Server not started')


def restart():
    stop()
    time.sleep(1)
    start()
    time.sleep(1)


def daemon():
    try:
        create_server()
    except Exception as e:
        logging.exception(e)


if __name__ == "__main__":
    num = len(sys.argv)
    if sys.argv[1] in (COMMANDS + ['daemon']):
        cmd = sys.argv[1]
        globals()[cmd]()
    else:
        logging.info('Error: invalid command')
        logging.info('Usage: python daemon.py {%s}.' % '|'.join(COMMANDS))
