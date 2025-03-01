import numpy as np
from funasr import AutoModel
from .asr_interface import ASRInterface
from .asr_with_vad import VoiceRecognitionVAD

import re
import soundfile as sf
import io
import torch

# paraformer-zh is a multi-functional asr model
# use vad, punc, spk or not as you need




class VoiceRecognition(ASRInterface):

    def __init__(
        self,
        model_name: str = "iic/SenseVoiceSmall",
        language: str = "auto",
        vad_model: str = "fsmn-vad",
        punc_model=None,
        ncpu: int = None,
        hub: str = None,
        device: str = "cpu",
        sample_rate: int = 16000,
        use_itn: bool = False,
    ) -> None:
        
        self.model = AutoModel(
            model=model_name,
            vad_model=vad_model,
            ncpu=ncpu,
            hub=hub,
            device=device,
            punc_model=punc_model,
            # spk_model="cam++",
        )
        self.sample_rate = sample_rate
        self.use_itn = use_itn
        self.language = language

        self.asr_with_vad = None

    def transcribe_with_local_vad(self) -> str:
        if self.asr_with_vad is None:
            self.asr_with_vad = VoiceRecognitionVAD(self.transcribe_np)
        return self.asr_with_vad.start_listening()
    
    def transcribe_np(self, audio: np.ndarray) -> str:
        
        audio_tensor = torch.tensor(audio, dtype=torch.float32)
        
        res = self.model.generate(
            input=audio_tensor,
            batch_size_s=300,
            use_itn=self.use_itn,
            language=self.language,
        )
        
        full_text = res[0]["text"]

        # SenseVoiceSmall may spits out some tags
        # like this: '<|zh|><|NEUTRAL|><|Speech|><|woitn|>欢迎大家来体验达摩院推出的语音识别模型'
        # we should remove those tags from the result

        # remove tags
        full_text = re.sub(r'<\|.*?\|>', '', full_text)
        # the tags can also look like '< | en | > < | EMO _ UNKNOWN | > < | S pe ech | > < | wo itn | > ', so...
        full_text = re.sub(r'< \|.*?\| >', '', full_text)
        
        return full_text.strip()

    def _numpy_to_wav_in_memory(self, numpy_array: np.ndarray, sample_rate):

        memory_file = io.BytesIO()
        sf.write(memory_file, numpy_array, sample_rate, format='WAV')
        memory_file.seek(0)
        
        return memory_file
