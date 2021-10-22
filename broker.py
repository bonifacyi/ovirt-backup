import json
import uuid
import os
from functools import partial

from main_daemon import start_daemon
from res import status, config_tool
import backup_tools
from res import app_logger
logger = app_logger.get_logger(__name__)


class MessageBroker:
    def __init__(self, message):
        self.message = json.loads(message)
        self.config = config_tool.ConfigTool()
        self.pid_file_name = self.__pid_file_generate()
        self.pid_file = os.path.join(self.config.get_pid_folder(), self.pid_file_name)
        self.active_pid = self.config.get_active_pid_file()

    def run(self):
        task = self.message['task']
        task_id = self.message['id']
        if task == 'status':
            status_dict = status.Status().get()
            return json.dumps(status_dict)
        elif task == 'backup':
            backup_function = partial(backup, self.message, task_id)
            start_daemon(pid_file=self.pid_file, partial_function=backup_function)
            pid = self.__get_pid()
            self.config.add_active_pid(task_id, pid)
            return pid
        elif task == 'cron_bkp':
            pass
        elif task == 'restore':
            restore_function = partial(restore, self.message, task_id)
            start_daemon(pid_file=self.pid_file, partial_function=restore_function)
            pid = self.__get_pid()
            self.config.add_active_pid(task_id, pid)
            return pid
        elif task == 'save_conf':
            pass
        elif task == 'load_conf':
            pass
        elif task == 'clean_conf':
            pass
        elif task == 'check_api':
            pass

    @staticmethod
    def __pid_file_generate():
        return 'ov-backup_' + uuid.uuid4().hex + '.pid'

    def __get_pid(self):
        with open(self.pid_file, 'r') as f:
            pid = f.read()
        return pid


def backup(settings, task_id):
    with backup_tools.Backup(settings=settings, task_id=task_id) as api_task:
        api_task.run()


def restore(settings, task_id):
    with backup_tools.Restore(settings=settings, task_id=task_id) as api_task:
        api_task.run()
