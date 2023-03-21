import collections
import webrtcvad
import time
import sys
#import torch
#import torchaudio
import numpy as np
#from asrot_server.s2s_transformer_pretrained import create_model_segmenter

def frame_generator(frame_duration_ms, audio, sample_rate, start_chunk):
    """Generates audio frames from PCM audio data.

    Takes the desired frame duration in milliseconds, the PCM data, and
    the sample rate.

    Yields Frames of the requested duration.
    """
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = start_chunk
    duration = (float(n) / sample_rate) / 2.0

    while offset + n <= len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += n
        offset += n

class Frame(object):
    """Represents a "frame" of audio data."""
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration

class AudioSegment():
    def __init__(self, start_time):
        self.time = start_time
        self.data = bytearray() #b''
        self.active = True
        self.completed = False

    def start_time(self):
        return self.time // (16*2)

    def end_time(self):
        return self.start_time() + self.size()

    def append(self, bytes):
        self.data += bytes

    def complete(self):
        self.completed = True

    def finish(self):
        self.active = False

    def get_all(self):
        return self.data

    def size(self):
        return len(self.data) // (16*2)

class Segmenter():
    def __init__(self, sample_rate, VAD_aggressive, padding_duration_ms, frame_duration_ms, rate_begin, rate_end):

        self.speech_filter = False
        if self.speech_filter == True:
            print("UTILIZE Speech Filter")
            self.speech_filter, self.speech_processor = create_model_segmenter( 'cpu', pretrained=False, config_path="/home/relater/workspace/AsrOT/AsrOT_backend/asrot_server/models/v2/config.json")
              #  dic = torch.load("./models/v2/epoch-49.pt", map_location=self.device)
            dic = torch.load("/home/relater/workspace/AsrOT/AsrOT_backend/asrot_server/models/v2/epoch-111.pt", map_location='cpu')

            self.speech_filter.load_state_dict(dic)
            self.speech_filter = self.speech_filter.to('cpu')
            self.speech_filter.eval()
            padding_duration_ms = 1000
            frame_duration_ms = 25
            rate_begin = 0.5
            rate_end = 0.9

        self.vad = webrtcvad.Vad(VAD_aggressive)
        self.padding_duration_ms = padding_duration_ms
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        num_padding_frames = int(self.padding_duration_ms / self.frame_duration_ms)
        self.triggered = False
        self.length_of_frame = int(self.sample_rate * (self.frame_duration_ms / 1000.0) * 2)
        self.rate_begin = rate_begin
        self.rate_end = rate_end

        self.segment = None
        self.segs = []
        self.ready = False 
        self.ring_buffer = collections.deque(maxlen=num_padding_frames)
        self.start_chunk = 0
        self.temp = b''


    def reset(self):
        if self.segment is not None:
            self.segment.complete()
        self.segment = None

        self.triggered = False
        self.temp = b''
        self.start_chunk = 0
        self.ring_buffer.clear()
        self.segs = []
        self.ready = True

    def active_seg(self):
        for pos, seg in enumerate(self.segs):
            if seg.active: return (seg, pos)
        return (None, len(self.segs))

    def determine_speech(self, speech_res):
        if speech_res == 2:
            return True
        else:
            return False

    def append_signal(self, audio):
        audio = self.temp + audio
        length_audio = len(audio) // self.length_of_frame * self.length_of_frame
        self.temp = audio[length_audio:]
        audio = audio[:length_audio]
        frames = frame_generator(self.frame_duration_ms, audio, self.sample_rate, self.start_chunk)
        frames = list(frames)
        self.start_chunk = self.start_chunk + len(audio)
        for j, frame in enumerate(frames):            
            is_speech = self.vad.is_speech(frame.bytes, self.sample_rate)
            if self.speech_filter:
                inp = np.frombuffer(frame.bytes, dtype='int16')
                processed_speech = torch.as_tensor(inp, dtype=torch.float32, device='cpu')
                processed_speech = ((processed_speech-processed_speech.mean())/processed_speech.std()).unsqueeze(0)
                speech_class = self.speech_filter(inputs=processed_speech).logits
                speech_res = speech_class.argmax(-1)
                is_speech = self.determine_speech(speech_res)
            if not self.triggered:
                self.ring_buffer.append((frame, is_speech))
                num_voiced = len([f for f, speech in self.ring_buffer if speech])

                if num_voiced >  self.rate_begin * self.ring_buffer.maxlen:
                    self.triggered = True
                    self.segment = AudioSegment(self.ring_buffer[0][0].timestamp)
                    for f, s in self.ring_buffer:
                        self.segment.append(f.bytes)
                    self.segs.append(self.segment)      
                    self.ring_buffer.clear()
            else:
                self.segment.append(frame.bytes)
                self.ring_buffer.append((frame, is_speech))
                num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])
                if num_unvoiced >  self.rate_end * self.ring_buffer.maxlen or self.segment.size()>900*30:
                    self.triggered = False
                    self.segment.complete()
                    self.ring_buffer.clear()


def get_segments(waveform, file_name):       
    #waveform, sample_rate = torchaudio.backend.sox_io_backend.load(wavfile,normalize=True)
    
    VAD_aggressive = 2
    padding_duration_ms = 450
    frame_duration_ms = 30
    rate_begin = 0.65
    rate_end = 0.55
    sample_rate = 16000

    segmenter = Segmenter(sample_rate, VAD_aggressive, padding_duration_ms, frame_duration_ms, rate_begin, rate_end)
    
    segmenter.reset()
    #segmenter.append_signal(waveform.numpy().tobytes())
    segmenter.append_signal(waveform)
    
    res = ""
    for seg in segmenter.segs:
        s = seg.start_time()
        e = seg.end_time()
        res += (file_name+"-%07d_%07d"%(s//10,e//10)+" "+file_name+" %.2f %.2f"%(s/1000,e/1000)+"\n")
    return res













