from django.conf import settings
import base64
import numpy as np
import threading

from . import worker_process as worker



collector_stt_ar = worker.Collector(worker.asr_ar_proc, "STT-AR", sort=True)
collector_stt_de = worker.Collector(worker.asr_de_proc, "STT-DE", sort=True)
collector_stt_en = worker.Collector(worker.asr_en_proc, "STT-EN", sort=True)
collector_stt_ua = worker.Collector(worker.asr_ua_proc, "STT-UA", sort=True)


"""
Specify the list of languages your ASR system supports by filling this list with tuples of code (max 5 chars) and display name.

Example:
LANGUAGE_CHOICES = [
    ('de', 'German'),
    ('en', 'English'),
]
"""
LANGUAGE_CHOICES = [
    ('de', 'German'),
    ('en', 'English'),
    ('ar', 'Arabic'),
]


"""
Specify the list of languages your MT system supports for a given source language.
You can do this by filling this dictionary with a source language key and a list of translations as values.
The translation lists of consist (similarly to the LANGUAGE_CHOICES) of tuples of code (max 5 chars) and display name.

Example:
TRANSLATION_CHOICES = {
    'de': [
        ('en', 'English'),
    ],
    'en': [
        ('de', 'German'),
        ('fr', 'French'),
    ],
}
"""
TRANSLATION_CHOICES = {
    'de': [],
    'en': [],
    'ar': [],
}


def do_adapt_for_worker(str_signal):
    try:
        x = np.frombuffer(base64.b64decode(str_signal+'==='),dtype="int16")
        return str_signal
    except Exception as e:
        print(e)
        b_signal = base64.b64decode(str_signal)
        #string_signal = " " + b_signal.decode()
        #b_signal = string_signal.encode()
        blank = " ".encode()
        b_signal = blank + b_signal
        b64_signal = base64.b64encode(b_signal)
        b64_str_signal =  b64_signal.decode('utf-8') + "\n"
        return b64_str_signal

"""
Implement your ASR worker interface in this function.
Please note that this functions is potentially called in parallel,
so if your workers rely on unique resources, you have to take care of synchronisation.

'source' is the content of the uploaded file.
'segmentation' is the content of the segmentation file.
'language' is one of the language codes specified in LANGUAGE_CHOICES.

Expects the result of the ASR process as (transcript, logging).
If there is any additional data/information, that you wish to pass to the mt processes, you can append them to the return tuple.
These will be passed as additional positional arguments to the mt worker function.
"""
def asr_worker(signal: bytes, segmentation: str, language: str) -> 'tuple[str]':
    signal = np.fromstring(signal, np.int16)

    if language == "en":
        collector = collector_stt_en
    elif language == "ar":
        collector = collector_stt_ar
    elif language == "de":
        collector = collector_stt_de
    elif language == "ua":
        collector = collector_stt_ua
    else:
        raise Exception('Unsupported language')

    results = ""
    for idx, line in enumerate(segmentation.splitlines()):
        print("{}/{}".format(idx, len(segmentation.splitlines())))
        line = line.strip()
        tokens = line.split()
        start = float(tokens[-2])
        end = float(tokens[-1])

        start = int(start * 16000)
        end = -1 if end <= 0. else int(end * 16000)
        if len(signal[start:end])<=1:
            continue
        if len(signal) < end:
            print("Segment ends at sec: {} audio signal ends at: {}/16000 sec".format(end, len(signal)))
            continue

        b_signal = signal[start:end]
        base64_signal = base64.b64encode(b_signal)
        str_signal = base64_signal.decode('latin-1')
        str_signal =  do_adapt_for_worker(str_signal)
        str_signal = str_signal.replace('\r', '').replace('\n', '')
        #str_signal = str_signal +"\t" +"\n"
        thread_id = threading.get_ident()
        c_req = {'data': str_signal, 'id': thread_id}
        collector.put(c_req)
        res = collector.get_res(thread_id)
        collector.del_id(thread_id)
        results += "{} {} {} \n".format(tokens[-2], tokens[-1], res)

    return results, "nothing"           


"""
Implement your MT worker interface in this function.
Please note that this functions is potentially called in parallel,
so if your workers rely on unique resources, you have to take care of synchronisation.

'text' is the result of the ASR worker.
'language' is one of the language codes specified in LANGUAGE_CHOICES.
'translations' is a list of language codes specified in TRANSLATION_CHOICES.
'args' is a list of the additional data/information returned by the asr process

Expects the results of all MT processes returned as (language_code, translation, logging) tuples.
They can either be returned as a list or using 'yield' (a generator).
"""
def mt_worker(text: str, language: str, translations: 'list[str]', *args) -> 'list[tuple[str,str]]':
    pass
