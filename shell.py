# coding: utf-8
from __future__ import print_function

import errno
import fcntl
import os
import select
import signal
import socket
import struct
import sys
import termios
import time
import tty

import paramiko
import subprocess


class SshTty(object):
    @staticmethod
    def get_win_size():
        """
        This function use to get the size of the windows!
        获得terminal窗口大小
        """
        if 'TIOCGWINSZ' in dir(termios):
            TIOCGWINSZ = termios.TIOCGWINSZ
        else:
            TIOCGWINSZ = 1074295912L
        s = struct.pack('HHHH', 0, 0, 0, 0)
        x = fcntl.ioctl(sys.stdout.fileno(), TIOCGWINSZ, s)
        return struct.unpack('HHHH', x)[0:2]

    @classmethod
    def set_win_size(self, sig, data):
        """
        This function use to set the window size of the terminal!
        设置terminal窗口大小
        """
        try:
            win_size = self.get_win_size()
            self.channel.resize_pty(height=win_size[0], width=win_size[1])
        except Exception:
            pass


class Connect(object):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.Tty = SshTty()

    def posix_shell(self):
        """
        Use paramiko channel connect server interactive.
        使用paramiko模块的channel，连接后端，进入交互式
        """
        old_tty = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            self.channel.settimeout(0.0)

            while True:
                try:
                    r, w, e = select.select([self.channel, sys.stdin], [], [])
                    flag = fcntl.fcntl(sys.stdin, fcntl.F_GETFL, 0)
                    fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL,
                                flag | os.O_NONBLOCK)
                except Exception:
                    pass

                if self.channel in r:
                    try:
                        x = self.channel.recv(10240)
                        if len(x) == 0:
                            break

                        index = 0
                        len_x = len(x)
                        while index < len_x:
                            try:
                                n = os.write(sys.stdout.fileno(), x[index:])
                                sys.stdout.flush()
                                index += n
                            except OSError as msg:
                                if msg.errno == errno.EAGAIN:
                                    continue

                    except socket.timeout:
                        pass

                if sys.stdin in r:
                    try:
                        x = os.read(sys.stdin.fileno(), 4096)
                    except OSError:
                        pass

                    if len(x) == 0:
                        break
                    self.channel.send(x)

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

    def conn(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(hostname=self.ip, port=self.port,
                    username='root', key_filename='/tmp/id_rsa')

        transport = ssh.get_transport()
        transport.set_keepalive(30)
        transport.use_compression(True)

        win_size = self.Tty.get_win_size()
        self.channel = channel = transport.open_session()
        channel.get_pty(term='xterm', height=win_size[0], width=win_size[1])
        channel.invoke_shell()

        try:
            signal.signal(signal.SIGWINCH, self.Tty.set_win_size)
        except Exception:
            pass

        self.posix_shell()

        channel.close()
        ssh.close()

    
if __name__ == '__main__':
    t = Connect('1.1.1.1', 22)
    t.conn()
