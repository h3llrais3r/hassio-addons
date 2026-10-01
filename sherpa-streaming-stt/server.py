#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tarfile
import tempfile
import time
import urllib.request
from functools import partial
from pathlib import Path

import numpy as np
import sherpa_onnx
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncServer, AsyncTcpServer

_LOGGER = logging.getLogger("sherpa_streaming_stt")
RATE = 16000
MODEL_ROOT = Path(os.environ.get("MODEL_ROOT", "/config/models"))
ASR_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{}"

# Profiles intentionally cover several streaming model families and variants.
# The archive names and model file layouts are from sherpa-onnx's published
# streaming model documentation/releases.
PROFILES = {
    "nemotron-80": {
        "name": "Nemotron 3.5 multilingual 80ms",
        "archive": "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-80ms-int8-2026-06-11.tar.bz2",
        "kind": "transducer",
        "files": {"encoder": "encoder.int8.onnx", "decoder": "decoder.int8.onnx", "joiner": "joiner.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["auto", "en-US", "en-GB", "es-US", "es-ES", "fr-FR", "fr-CA", "it-IT", "pt-BR", "pt-PT", "nl-NL", "de-DE", "tr-TR", "ru-RU", "ar-AR", "hi-IN", "ja-JP", "ko-KR", "vi-VN", "uk-UA", "pl-PL", "sv-SE", "cs-CZ", "nb-NO", "da-DK", "bg-BG", "fi-FI", "hr-HR", "sk-SK", "zh-CN", "hu-HU", "ro-RO", "et-EE"],
        "adaptation_only": ["el-GR", "lt-LT", "lv-LV", "mt-MT", "sl-SI", "he-IL", "th-TH", "nn-NO"],
        "language_option": True,
    },
    "nemotron-160": {
        "name": "Nemotron 3.5 multilingual 160ms",
        "archive": "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-160ms-int8-2026-06-11.tar.bz2",
        "kind": "transducer",
        "files": {"encoder": "encoder.int8.onnx", "decoder": "decoder.int8.onnx", "joiner": "joiner.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["auto", "en-US", "en-GB", "es-US", "es-ES", "fr-FR", "fr-CA", "it-IT", "pt-BR", "pt-PT", "nl-NL", "de-DE", "tr-TR", "ru-RU", "ar-AR", "hi-IN", "ja-JP", "ko-KR", "vi-VN", "uk-UA", "pl-PL", "sv-SE", "cs-CZ", "nb-NO", "da-DK", "bg-BG", "fi-FI", "hr-HR", "sk-SK", "zh-CN", "hu-HU", "ro-RO", "et-EE"],
        "adaptation_only": ["el-GR", "lt-LT", "lv-LV", "mt-MT", "sl-SI", "he-IL", "th-TH", "nn-NO"],
        "language_option": True,
    },
    "nemotron-560": {
        "name": "Nemotron 3.5 multilingual 560ms",
        "archive": "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11.tar.bz2",
        "kind": "transducer",
        "files": {"encoder": "encoder.int8.onnx", "decoder": "decoder.int8.onnx", "joiner": "joiner.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["auto", "en-US", "en-GB", "es-US", "es-ES", "fr-FR", "fr-CA", "it-IT", "pt-BR", "pt-PT", "nl-NL", "de-DE", "tr-TR", "ru-RU", "ar-AR", "hi-IN", "ja-JP", "ko-KR", "vi-VN", "uk-UA", "pl-PL", "sv-SE", "cs-CZ", "nb-NO", "da-DK", "bg-BG", "fi-FI", "hr-HR", "sk-SK", "zh-CN", "hu-HU", "ro-RO", "et-EE"],
        "adaptation_only": ["el-GR", "lt-LT", "lv-LV", "mt-MT", "sl-SI", "he-IL", "th-TH", "nn-NO"],
        "language_option": True,
    },
    "nemotron-1120": {
        "name": "Nemotron 3.5 multilingual 1120ms",
        "archive": "sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-1120ms-int8-2026-06-11.tar.bz2",
        "kind": "transducer",
        "files": {"encoder": "encoder.int8.onnx", "decoder": "decoder.int8.onnx", "joiner": "joiner.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["auto", "en-US", "en-GB", "es-US", "es-ES", "fr-FR", "fr-CA", "it-IT", "pt-BR", "pt-PT", "nl-NL", "de-DE", "tr-TR", "ru-RU", "ar-AR", "hi-IN", "ja-JP", "ko-KR", "vi-VN", "uk-UA", "pl-PL", "sv-SE", "cs-CZ", "nb-NO", "da-DK", "bg-BG", "fi-FI", "hr-HR", "sk-SK", "zh-CN", "hu-HU", "ro-RO", "et-EE"],
        "adaptation_only": ["el-GR", "lt-LT", "lv-LV", "mt-MT", "sl-SI", "he-IL", "th-TH", "nn-NO"],
        "language_option": True,
    },
    "zipformer-en": {
        "name": "Zipformer streaming English (2023-06-26)",
        "archive": "sherpa-onnx-streaming-zipformer-en-2023-06-26.tar.bz2",
        "kind": "transducer",
        "files": {"encoder": "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx", "decoder": "decoder-epoch-99-avg-1-chunk-16-left-128.onnx", "joiner": "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["en-US", "en-GB"],
        "language_option": False,
    },
    "zipformer-fr": {
        "name": "Zipformer streaming French (2023-04-14)",
        "archive": "sherpa-onnx-streaming-zipformer-fr-2023-04-14.tar.bz2",
        "kind": "transducer",
        "files": {"encoder": "encoder-epoch-29-avg-9-with-averaged-model.int8.onnx", "decoder": "decoder-epoch-29-avg-9-with-averaged-model.onnx", "joiner": "joiner-epoch-29-avg-9-with-averaged-model.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["fr-FR", "fr-CA"],
        "language_option": False,
    },
    "zipformer-zh-en": {
        "name": "Zipformer streaming Chinese + English (2023-02-20)",
        "archive": "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2",
        "kind": "transducer",
        "files": {"encoder": "encoder-epoch-99-avg-1.int8.onnx", "decoder": "decoder-epoch-99-avg-1.onnx", "joiner": "joiner-epoch-99-avg-1.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["zh-CN", "en-US"],
        "language_option": False,
    },
    "paraformer-zh-en": {
        "name": "Streaming Paraformer Chinese + English",
        "archive": "sherpa-onnx-streaming-paraformer-bilingual-zh-en.tar.bz2",
        "kind": "paraformer",
        "files": {"encoder": "encoder.int8.onnx", "decoder": "decoder.int8.onnx", "tokens": "tokens.txt"},
        "languages": ["zh-CN", "en-US"],
        "language_option": False,
    },
}



def options():
    with open("/data/options.json", "r", encoding="utf-8") as f:
        return json.load(f)


def download_and_extract(profile_id: str) -> Path:
    profile = PROFILES[profile_id]
    archive_name = profile["archive"]
    name = archive_name[:-8] if archive_name.endswith(".tar.bz2") else archive_name
    dest = MODEL_ROOT / name
    required = [dest / rel for rel in profile["files"].values()]
    if all(p.is_file() for p in required):
        return dest

    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    archive = MODEL_ROOT / archive_name
    tmp = MODEL_ROOT / (archive_name + ".download")
    url = ASR_URL.format(archive_name)
    _LOGGER.info("Downloading model %s from %s", profile_id, url)
    try:
        with urllib.request.urlopen(url, timeout=300) as src, tmp.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        tmp.replace(archive)
        with tempfile.TemporaryDirectory(dir=MODEL_ROOT) as td_name:
            td = Path(td_name)
            with tarfile.open(archive, "r:bz2") as tar:
                base = td.resolve()
                for member in tar.getmembers():
                    target = (base / member.name).resolve()
                    if os.path.commonpath((str(base), str(target))) != str(base):
                        raise RuntimeError(f"Unsafe model archive member: {member.name}")
                tar.extractall(td)
            extracted = td / name
            if not extracted.is_dir():
                dirs = [p for p in td.iterdir() if p.is_dir()]
                if len(dirs) != 1:
                    raise RuntimeError("Unexpected model archive layout")
                extracted = dirs[0]
            if not all((extracted / rel).is_file() for rel in profile["files"].values()):
                raise RuntimeError(f"Model archive {archive_name} is missing required files")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(extracted), str(dest))
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def create_recognizer(profile_id: str, model_dir: Path, threads: int, beam_size: int):
    p = PROFILES[profile_id]
    f = p["files"]
    if p["kind"] == "paraformer":
        return sherpa_onnx.OnlineRecognizer.from_paraformer(
            tokens=str(model_dir / f["tokens"]),
            encoder=str(model_dir / f["encoder"]),
            decoder=str(model_dir / f["decoder"]),
            num_threads=threads,
            sample_rate=RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            provider="cpu",
        )

    method = "modified_beam_search" if beam_size > 1 else "greedy_search"
    return sherpa_onnx.OnlineRecognizer.from_transducer(
        encoder=str(model_dir / f["encoder"]),
        decoder=str(model_dir / f["decoder"]),
        joiner=str(model_dir / f["joiner"]),
        tokens=str(model_dir / f["tokens"]),
        num_threads=threads,
        sample_rate=RATE,
        feature_dim=80,
        provider="cpu",
        decoding_method=method,
        max_active_paths=max(beam_size, 1),
    )


def measure_tail_padding(recognizer) -> int:
    # Conservative tail for streaming models. This is only used to flush the
    # final buffered audio and does not affect the live decode path.
    return int(0.66 * RATE)


class Session:
    def __init__(self, recognizer, tail_samples: int, language: str, language_option: bool):
        self.recognizer = recognizer
        self.tail_samples = tail_samples
        self.stream = recognizer.create_stream()
        if language_option and language and language != "auto":
            self.stream.set_option("language", language)
        elif language_option and language == "auto":
            self.stream.set_option("language", "auto")
        self.leftover = b""
        self.audio_samples = 0
        self.started = time.monotonic()

    def accept(self, pcm: bytes):
        pcm = self.leftover + pcm
        if len(pcm) % 2:
            self.leftover = pcm[-1:]
            pcm = pcm[:-1]
        else:
            self.leftover = b""
        if pcm:
            samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            self.audio_samples += len(samples)
            self.stream.accept_waveform(RATE, samples)
            while self.recognizer.is_ready(self.stream):
                self.recognizer.decode_stream(self.stream)

    def result(self):
        if self.leftover:
            samples = np.frombuffer(self.leftover + b"\x00", dtype=np.int16).astype(np.float32) / 32768.0
            self.audio_samples += len(samples)
            self.stream.accept_waveform(RATE, samples)
            self.leftover = b""
        self.stream.accept_waveform(RATE, np.zeros(self.tail_samples, dtype=np.float32))
        self.stream.input_finished()
        while self.recognizer.is_ready(self.stream):
            self.recognizer.decode_stream(self.stream)
        text = self.recognizer.get_result(self.stream)
        elapsed = max(time.monotonic() - self.started, 1e-6)
        audio_seconds = self.audio_samples / RATE
        rtf = elapsed / audio_seconds if audio_seconds else 0.0
        return text, audio_seconds, elapsed, rtf


class Handler(AsyncEventHandler):
    def __init__(self, info: Info, recognizer, tail_samples: int, profile_id: str, default_language: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info_event = info.event()
        self.recognizer = recognizer
        self.tail_samples = tail_samples
        self.profile = PROFILES[profile_id]
        self.profile_id = profile_id
        self.default_language = default_language
        self.language = default_language
        self.converter = AudioChunkConverter(rate=RATE, width=2, channels=1)
        self.session = None
        self.got_audio = False

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.info_event)
            return True

        if Transcribe.is_type(event.type):
            req = Transcribe.from_event(event)
            self.language = req.language or self.default_language
            if self.language not in self.profile["languages"]:
                supported = ", ".join(self.profile["languages"])
                raise ValueError(f"Language {self.language!r} is not supported by model {self.profile_id}. Supported: {supported}")
            return True

        if AudioStart.is_type(event.type):
            self.session = Session(self.recognizer, self.tail_samples, self.language, self.profile["language_option"])
            self.got_audio = False
            return True

        if AudioChunk.is_type(event.type):
            if self.session is None:
                self.session = Session(self.recognizer, self.tail_samples, self.language, self.profile["language_option"])
            chunk = self.converter.convert(AudioChunk.from_event(event))
            self.got_audio = True
            await asyncio.to_thread(self.session.accept, chunk.audio)
            return True

        if AudioStop.is_type(event.type):
            if not self.got_audio or self.session is None:
                await self.write_event(Transcript(text="").event())
                return False
            text, audio_s, elapsed_s, rtf = await asyncio.to_thread(self.session.result)
            _LOGGER.info("[%s] %.2fs audio -> %.3fs processing, RTF %.3f: %s", self.profile_id, audio_s, elapsed_s, rtf, text)
            out_language = self.language if self.profile["language_option"] else (self.profile["languages"][0] if self.profile["languages"] else None)
            await self.write_event(Transcript(text=text, language=out_language).event())
            return False

        return True


async def main():
    cfg = options()
    profile_id = cfg.get("model", "nemotron-560")
    if profile_id not in PROFILES:
        raise ValueError(f"Unknown model profile: {profile_id}")
    profile = PROFILES[profile_id]
    language = cfg.get("language", "auto")
    threads = int(cfg.get("num_threads", 4))
    beam_size = int(cfg.get("beam_size", 4))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    model_dir = download_and_extract(profile_id)
    _LOGGER.info("Loading model profile %s from %s", profile_id, model_dir)
    recognizer = create_recognizer(profile_id, model_dir, threads, beam_size)
    tail = measure_tail_padding(recognizer)

    models = []
    for pid, p in PROFILES.items():
        models.append(AsrModel(
            name=pid,
            description=p["name"],
            attribution=Attribution(name="k2-fsa sherpa-onnx / model authors", url="https://github.com/k2-fsa/sherpa-onnx"),
            installed=(pid == profile_id),
            languages=p["languages"],
            version=p["archive"],
        ))

    info = Info(asr=[AsrProgram(
        name="sherpa-streaming-stt",
        description="Generic streaming ASR using multiple sherpa-onnx online model families",
        attribution=Attribution(name="k2-fsa sherpa-onnx", url="https://github.com/k2-fsa/sherpa-onnx"),
        installed=True,
        supports_transcript_streaming=False,
        requires_external_vad=True,
        models=models,
    )])

    # The service always listens on the fixed container port.
    # Home Assistant maps the container port to the host port configured in
    # the add-on Network settings (10301 by default).
    container_port = 10300
    server = AsyncServer.from_uri(f"tcp://0.0.0.0:{container_port}")
    if cfg.get("zeroconf", True) and isinstance(server, AsyncTcpServer):
        from wyoming.zeroconf import HomeAssistantZeroconf
        zc = HomeAssistantZeroconf(name="Sherpa Streaming STT", port=server.port, host=server.host)
        await zc.register_server()
        _LOGGER.info("Wyoming Zeroconf discovery enabled")

    _LOGGER.info("Ready: model=%s language=%s threads=%d beam=%d", profile_id, language, threads, beam_size)
    await server.run(partial(Handler, info, recognizer, tail, profile_id, language))


if __name__ == "__main__":
    asyncio.run(main())
