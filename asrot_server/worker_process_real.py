import os
import subprocess
from django.conf import settings
import threading as thrd
import logging
#import atexit
import signal


asr_de_err_file = open(os.path.join(settings.BASE_DIR, 'worker_log', 'asr_de.log'), 'a+')
asr_ar_err_file = open(os.path.join(settings.BASE_DIR, 'worker_log', 'asr_ar.log'), 'a+')
asr_en_err_file = open(os.path.join(settings.BASE_DIR, 'worker_log', 'asr_en.log'), 'a+')


node="i13hpc62"
gpu=0
asr_de_proc = subprocess.Popen('/home/relater/workspace/asr_online_tool/Lecture_Translator/LT_UI/worker_scripts/decode_sig.sh {} {} de'.format(node, gpu),
                                 shell=True, encoding="utf-8", bufsize=0, universal_newlines=False, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=asr_de_err_file)

asr_ar_proc = subprocess.Popen('/home/relater/workspace/asr_online_tool/Lecture_Translator/LT_UI/worker_scripts/decode_sig.sh {} {} ar'.format(node,gpu),
                                 shell=True, encoding="utf-8", bufsize=0, universal_newlines=False, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=asr_ar_err_file)
asr_en_proc = subprocess.Popen('/home/relater/workspace/asr_online_tool/Lecture_Translator/LT_UI/worker_scripts/decode_sig.sh {} {} en'.format(node,gpu),
                                 shell=True, encoding="utf-8", bufsize=0, universal_newlines=False, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=asr_en_err_file)


import time
from threading import Thread
import threading
import queue

class Collector:

    def __init__(self, worker, name, sort=False):
        self.c_req_q = queue.Queue()
       
        self.res_d = {}
        self.name = name
        self.worker = worker
        self.sort = sort

        self.input_num = 0
        self.history_in = list()
        self.history_out = list()

        self.run()

    def sort_data(self, c_req_list):
        lst = sorted(c_req_list, key=lambda c_req: c_req.size)
        return lst      

    def put(self, c_req):
        self.c_req_q.put(c_req)

    def process_data(self):
        print("{}: collector startet and process_data entered.".format(self.name))

        while True:
            c_req_list = self.c_req_q.get()
            print("{}: requests in queue waiting: {}".format(self.name, self.c_req_q.qsize()))
            
            if type(c_req_list) != list:
                c_req_list = [c_req_list]
            len_c_req_q = self.c_req_q.qsize()
            batch_size = min(len_c_req_q, 4)

            for _ in range(batch_size):
                c_req_list.append(self.c_req_q.get())
            #time.sleep(5)
            print("{}: requests in queue waiting after reading a batch of 5: {}".format(self.name, self.c_req_q.qsize()))
            print("{}: after SLEEP".format(self.name))
            id_list = list()
            lines = list()
          #  test_mt_lock.acquire()

            if self.sort:
                c_req_list = sorted(c_req_list, key=lambda el: len(el['data']), reverse=True)

            #for c_req_ in c_req_list:
             #   print(len(c_req_['data']))

            for c_req in c_req_list:
                id_list.append(c_req['id'])
                lines.append(c_req['data'].replace('\r', '').replace('\n', ''))
          
            self.input_num = len(c_req_list)
            self.history_in = c_req_list

            joined_lines = '\t'.join([line for line in lines])
            joined_lines = joined_lines + '\n'
           
            print("{}: write to worker batch size: {}".format(self.name, len(lines)))
            self.worker.stdin.write(joined_lines)
            self.worker.stdin.flush()
            res = "worker did not yield any result"

            for line in self.worker.stdout:
                res = line

                if len(res)<500:
                    print("{}: res: {}".format(self.name, res))
                break

            if res.count('\\t') > 0:
                res = res.split('\\t')
            else:
                res = res.split('\t')

            self.history_out =res

           # if self.input_num != len(res):
           #     logger.error("=====")
           #     logger.error("=====")
           #     logger.error("Worker name: {}".format(self.name))
           #     logger.error("Input history: {} ".format(self.history_in))
           #     logger.error("=====")
           #     logger.error("Output history: {}".format(self.history_out))
           #     logger.error("=====")
           #     logger.error("=====")

            #logger.info("{}: recieved number of results: {}".format(self.name, len(res)))
            print("{}: recieved number of results: {}".format(self.name, len(res)))
            print(id_list)
            print(self.res_d)
                               
            for i in range(len(res)):
                self.res_d[id_list[i]].put(res[i])

    def get_res(self, key):
        if key not in self.res_d:
            self.res_d[key] = queue.Queue()         

        return self.res_d[key].get()

    def del_id(self, key):
        del self.res_d[key]

    def run(self):
        thread = Thread(target = self.process_data)
        thread.start()


def cleanup(signal=None, frame=None):
    print("CLEANING UP")
    logger.info("CLEANING UP BEFORE SHUT DOWN...")
    asr_de_proc.kill()
    asr_ar_proc.kill()
    mt_ar_de_proc.kill()
    mt_de_ar_proc.kill()
    tts_de_proc.kill()
    tts_ar_proc.kill()
#atexit.register(cleanup)
#signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)
