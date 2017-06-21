# -*- coding: utf-8 -*-

# IPC: A python library for interprocess communication via standard streams.
#
# $Id$
#
# License: MIT
# Copyright 2015-2017 Ruslan V. Uss (https://github.com/UncleRus)
# Copyright 2017 Oleg Golovanov (https://github.com/oleg-golovanov)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

__version__ = '1.1.2'

import sys
import time
import json
import subprocess
import functools
import threading
import os
import signal
import logging

if sys.version_info[0] == 2:
    from Queue import Queue, Empty
else:
    from queue import Queue, Empty


class AttrDict(dict):

    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


def detach(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.setDaemon(True)
    thread.start()

    return thread


def channel(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)
    wrapped.channel = True

    return wrapped


class Message(object):

    def __init__(self, name, channel=None, **kwargs):
        self.name = name
        self.channel = channel
        self.args = AttrDict(kwargs)

    def dumps(self):
        return json.dumps({'name': self.name, 'args': self.args})

    def write(self, stream):
        stream.write('{}\n'.format(self.dumps()))
        stream.flush()

    def __eq__(self, other):
        return self.name == other.name and self.args == other.args

    def __repr__(self):
        return '<Message name=%r, channel=%r, args=%r>' % (self.name, self.channel, self.args)

    @classmethod
    def parse(cls, line, channel):
        try:
            data = json.loads(line)
        except ValueError:
            if line:
                return cls('jsonerr', channel, msg=line)
            raise
        else:
            return cls(data['name'], channel, **data['args'])


class Process(object):

    def __init__(self, *args, interval=0.01):
        self.args = args
        self.interval = interval
        self.output = Queue()
        self.input = Queue()
        self.thread = None
        self.running = False
        self.proc = None

    def is_alive(self):
        return self.proc and self.proc.poll() is None

    def start(self):
        if self.thread:
            raise RuntimeError('Already started')
        self.proc = subprocess.Popen(
            self.args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.running = True
        self.thread = detach(self.run)

    def stop(self):
        if not self.thread:
            return
        self.running = False
        self.thread.join()

    def reset(self):
        if self.is_alive():
            self.stop()
        self.kill()
        self.input = Queue()
        self.output = Queue()
        self.start()

    def terminate(self):
        if not self.is_alive():
            return
        try:
            self.proc.terminate()
        except:
            pass
        self.running = False
        if self.thread:
            self.thread.join()

    def kill(self):
        if not self.is_alive():
            return
        try:
            self.proc.kill()
        except:
            pass
        self.running = False
        if self.thread:
            self.thread.join()

    def read(self):
        try:
            return self.output.get_nowait()
        except Empty:
            return None

    def write(self, name, **kwargs):
        self.input.put(name if isinstance(name, Message) else Message(name, **kwargs))

    def _reader(self, stream, datatype):
        try:
            for line in iter(stream.readline, b''):
                try:
                    self.output.put(Message.parse(line, datatype))
                except:
                    pass
            stream.close()
        except IOError:
            pass

    def _writer(self):
        while self.is_alive():
            try:
                self.input.get_nowait().write(self.proc.stdin)
            except:
                pass
            time.sleep(self.interval)
        self.proc.stdin.close()

    def process_messages(self):
        while True:
            msg = self.read()
            if not msg:
                return

            method = getattr(self, 'on_msg_%s' % msg.name)
            if hasattr(method, 'channel'):
                method(channel=msg.channel, **msg.args)
            else:
                method(**msg.args)

    def run(self):
        detach(self._writer)
        out_thread = detach(self._reader, self.proc.stdout, 'out')
        err_thread = detach(self._reader, self.proc.stderr, 'err')
        self.on_started()

        while self.running and self.proc.poll() is None:
            self.process_messages()
            time.sleep(self.interval)

        if self.proc.poll() is None:
            self.proc.terminate()

        term = self.running

        out_thread.join()
        err_thread.join()

        self.running = False
        self.thread = None

        if term:
            self.on_terminated()
        else:
            self.on_stopped()

    def on_terminated(self):
        pass

    def on_stopped(self):
        pass

    def on_started(self):
        pass


class Interface(object):

    def __init__(self, on_stdin_error=None):
        self.on_stdin_error = on_stdin_error

        self.stdin = Queue()
        self.stdout = Queue()
        self.stderr = Queue()

        self.stdin_thread = None
        self.stdout_thread = None
        self.stderr_thread = None

        self.running = False
        self.start()

    def reader(self):
        while self.running:
            try:
                line = sys.stdin.readline()
                if not line:
                    return
                msg = Message.parse(line, 'in')
                self.stdin.put(msg)
            except Exception as e:
                if callable(self.on_stdin_error):
                    self.on_stdin_error(self, e)

    def writer(self, q, stream):
        while self.running:
            try:
                q.get(timeout=0.1).write(stream)
                stream.flush()
            except Empty:
                pass

    def start(self):
        if self.running:
            raise RuntimeError('Application is already running')

        self.running = True

        # Создаем треды для обмена с внешним миром
        self.stdin_thread = detach(self.reader)
        self.stdout_thread = detach(self.writer, self.stdout, sys.stdout)
        self.stderr_thread = detach(self.writer, self.stderr, sys.stderr)

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.stdout_thread.join()
        self.stderr_thread.join()
        sys.exit()

    def write(self, message, stderr=False):
        (self.stderr if stderr else self.stdout).put(message)

    def read(self):
        try:
            return self.stdin.get_nowait()
        except Empty:
            return None


try:
    __sigkill = signal.SIGKILL
except:
    __sigkill = signal.SIGTERM


class Worker(object):

    def __init__(self, pid_file, logger=None):
        self.iface = Interface(self.on_stdin_error)
        self.pid_file = pid_file
        self.logger = logger
        signal.signal(signal.SIGINT, self.on_sigint)

    def log(self, *args, **kwargs):
        if self.logger:
            self.logger.log(*args, **kwargs)

    def kill_copy(self):
        try:
            with open(self.pid_file) as f:
                pid = int(f.read())
                self.log(logging.INFO, 'Killing already running instance with PID %d...' % pid)
                os.kill(pid, __sigkill)
        except:
            pass

    def on_stdin_error(self, e):
        self.log(logging.ERROR, 'STDIN read error: %r' % e)

    def on_sigint(self, *args, **kwargs):
        self.log(logging.INFO, 'Got SIGINT, exiting')
        self.exit()

    def start(self):

        # trying to kill alredy running instance
        self.kill_copy()

        # writing PID to file
        with open(self.pid_file, 'wb') as f:
            f.write(str(os.getpid()))

        self.log(logging.INFO, 'Started')

    def exit(self):
        self.iface.stop()
        try:
            os.remove(self.pid_file)
        except:
            pass


__all__ = (
    'Process', 'Interface', 'Message', 'channel', 'Worker'
)


