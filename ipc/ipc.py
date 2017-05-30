# -*- coding: utf-8 -*-


import sys
import time
import json
import Queue
import subprocess

import util


class Message(object):

    def __init__(self, name, channel=None, **kwargs):
        self.name = name
        self.channel = channel
        self.args = util.AttrDict(kwargs)

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


class Signal(object):

    def __init__(self, append_sender=True):
        self.slots = {}
        self._owner = None
        self.append_sender = append_sender

    def __get__(self, obj, cls=None):
        self._owner = obj
        return self

    def _check(self):
        if not self._owner:
            raise RuntimeError('Signal is not bounded')

    def _connect(self, slot):
        if not callable(slot):
            raise TypeError('Slot is not callable')
        if self._owner not in self.slots:
            self.slots[self._owner] = []
        if slot not in self.slots[self._owner]:
            self.slots[self._owner].append(slot)

    def connect(self, slot):
        self._check()
        self._connect(slot)

    def connect_async(self, slot):
        self._check()
        self._connect(util.async_wrapper(slot))

    def disconnect(self, slot):
        self._check()
        try:
            self.slots[self._owner].remove(slot)
        except (ValueError, KeyError):
            pass

    def clear(self):
        self._check()
        if self._owner in self.slots:
            del self.slots[self._owner]

    def emit(self, *args, **kwargs):
        self._check()
        if self.append_sender:
            args = (self._owner,) + args
        for slot in self.slots.get(self._owner, []):
            slot(*args, **kwargs)


class Process(object):

    def __init__(self, *args):
        self.args = args
        self.output = Queue.Queue()
        self.input = Queue.Queue()
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
        self.thread = util.detach(self.run)

    def stop(self):
        if not self.thread:
            return
        self.running = False
        self.thread.join()

    def reset(self):
        if self.is_alive():
            self.stop()
        self.kill()
        self.input = Queue.Queue()
        self.output = Queue.Queue()
        self.start()

    def terminate(self):
        if not self.is_alive():
            return
        try:
            self.proc.terminate()
        except Exception:
            pass
        self.running = False
        if self.thread:
            self.thread.join()

    def kill(self):
        if not self.is_alive():
            return
        try:
            self.proc.kill()
        except Exception:
            pass
        self.running = False
        if self.thread:
            self.thread.join()

    def read(self):
        try:
            return self.output.get_nowait()
        except Queue.Empty:
            return None

    def write(self, name, **kwargs):
        self.input.put(name if isinstance(name, Message) else Message(name, **kwargs))

    def _reader(self, stream, datatype):
        try:
            for line in iter(stream.readline, b''):
                try:
                    self.output.put(Message.parse(line, datatype))
                except Exception:
                    pass
            stream.close()
        except IOError:
            pass

    def _writer(self):
        while self.is_alive():
            try:
                self.input.get_nowait().write(self.proc.stdin)
            except Exception:
                pass
            time.sleep(0.01)
        self.proc.stdin.close()

    def process_messages(self):
        msg = self.read()
        if not msg:
            return

        method = getattr(self, 'on_msg_%s' % msg.name)
        if hasattr(method, 'channel'):
            method(channel=msg.channel, **msg.args)
        else:
            method(**msg.args)

    def run(self):
        util.detach(self._writer)
        out_thread = util.detach(self._reader, self.proc.stdout, 'out')
        err_thread = util.detach(self._reader, self.proc.stderr, 'err')
        self.on_started()

        while self.running and self.proc.poll() is None:
            self.process_messages()
            time.sleep(0.01)

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


class SubprocessInterface(object):
    stdin_error = Signal()

    def __init__(self):
        self.stdin = Queue.Queue()
        self.stdout = Queue.Queue()
        self.stderr = Queue.Queue()

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
                self.stdin_error.emit(e)

    def writer(self, queue, stream):
        while self.running:
            try:
                queue.get(timeout=0.1).write(stream)
                stream.flush()
            except Queue.Empty:
                pass

    def start(self):
        if self.running:
            raise RuntimeError('Application is running already')

        self.running = True

        # Создаем треды для обмена с внешним миром
        self.stdin_thread = util.detach(self.reader)
        self.stdout_thread = util.detach(self.writer, self.stdout, sys.stdout)
        self.stderr_thread = util.detach(self.writer, self.stderr, sys.stderr)

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
        except Queue.Empty:
            return None
