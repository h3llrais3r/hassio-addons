#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from functools import partial
from pathlib import Path
from urllib.parse import quote

import numpy as np
import sherpa_onnx
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import AsrModel, AsrProgram, Attribution, Describe, Info
from wyoming.server import AsyncEventHandler, AsyncServer, AsyncTcpServer

_LOGGER = logging.getLogger("sherpa_onnx_stt")
ADDON_VERSION = os.environ.get("ADDON_VERSION", "unknown")
MODEL_ROOT = Path(os.environ.get("MODEL_ROOT", "/config/models"))
GITHUB_API = "https://api.github.com/repos/k2-fsa/sherpa-onnx"
RELEASE_TAG = "asr-models"
RATE = 16000
CATALOG_CACHE = MODEL_ROOT / ".asr-models-catalog.json"
CATALOG_CACHE_MAX_AGE = 24 * 60 * 60
SUPPORTED_MODEL_TYPES = ("auto", "online_transducer", "offline_transducer")
SUPPORTED_ARCHIVES = (".tar.bz2", ".tar.gz", ".tgz", ".zip")


def options():
    with open("/data/options.json", "r", encoding="utf-8") as f:
        return json.load(f)


def github_json(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sherpa-onnx-stt-home-assistant-addon",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def get_catalogue(force_refresh: bool = False) -> list[dict]:
    """Read the official Sherpa ASR release assets, with a 24-hour local cache."""
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)

    if not force_refresh and CATALOG_CACHE.is_file():
        age = time.time() - CATALOG_CACHE.stat().st_mtime
        if age < CATALOG_CACHE_MAX_AGE:
            try:
                cached = json.loads(CATALOG_CACHE.read_text(encoding="utf-8"))
                if isinstance(cached, list):
                    return cached
            except (OSError, json.JSONDecodeError):
                pass

    release_url = f"{GITHUB_API}/releases/tags/{quote(RELEASE_TAG)}"
    release = github_json(release_url)
    release_id = release.get("id")
    if not release_id:
        raise RuntimeError("GitHub did not return the official Sherpa ASR release")

    assets: list[dict] = []
    page = 1
    while True:
        url = f"{GITHUB_API}/releases/{release_id}/assets?per_page=100&page={page}"
        batch = github_json(url)
        if not isinstance(batch, list):
            raise RuntimeError("Unexpected response while reading Sherpa ASR catalogue")
        assets.extend(
            {
                "name": item.get("name", ""),
                "url": item.get("browser_download_url", ""),
                "size": int(item.get("size", 0)),
                "updated_at": item.get("updated_at", ""),
            }
            for item in batch
            if item.get("name", "").lower().endswith(SUPPORTED_ARCHIVES)
            and item.get("browser_download_url")
        )
        if len(batch) < 100:
            break
        page += 1

    assets.sort(key=lambda item: item["name"].lower())
    temp = CATALOG_CACHE.with_suffix(".tmp")
    temp.write_text(json.dumps(assets, indent=2), encoding="utf-8")
    temp.replace(CATALOG_CACHE)
    return assets


def log_catalogue(assets: list[dict]):
    _LOGGER.info("Official Sherpa-ONNX ASR catalogue (%d downloadable archives):", len(assets))
    for asset in assets:
        size_mb = asset["size"] / (1024 * 1024)
        _LOGGER.info("  %s (%.1f MB)", asset["name"], size_mb)


def safe_model_name(archive_name: str) -> str:
    # The name is also used as a directory name; never accept path components.
    if Path(archive_name).name != archive_name or not archive_name:
        raise ValueError("model_archive must be an exact archive filename, not a path")
    return re.sub(r"[^A-Za-z0-9._-]", "_", archive_name)


def download_archive(asset: dict, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial_path = destination.with_name(destination.name + ".download")
    request = urllib.request.Request(
        asset["url"],
        headers={"User-Agent": "sherpa-onnx-stt-home-assistant-addon"},
    )
    _LOGGER.info(
        "Downloading official Sherpa model archive %s (%.1f MB)",
        asset["name"], asset["size"] / (1024 * 1024),
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response, partial_path.open("wb") as output:
            total = int(response.headers.get("Content-Length", asset["size"] or 0))
            downloaded = 0
            last_log = time.monotonic()
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_log >= 2:
                    if total:
                        _LOGGER.info("Model download: %.1f%%", downloaded * 100 / total)
                    else:
                        _LOGGER.info("Model download: %.1f MB", downloaded / (1024 * 1024))
                    last_log = now
        if asset["size"] and destination.stat().st_size != asset["size"]:
            raise RuntimeError(
                f"Downloaded archive size mismatch for {asset['name']}: "
                f"expected {asset['size']} bytes, got {destination.stat().st_size}"
            )
        partial_path.replace(destination)
    finally:
        partial_path.unlink(missing_ok=True)


def _safe_extract_tar(archive: Path, destination: Path):
    with tarfile.open(archive, "r:*") as tar:
        root = destination.resolve()
        for member in tar.getmembers():
            target = (root / member.name).resolve()
            if os.path.commonpath((str(root), str(target))) != str(root):
                raise RuntimeError(f"Unsafe path in model archive: {member.name}")
            if member.issym() or member.islnk():
                raise RuntimeError(f"Links are not allowed in model archive: {member.name}")
        tar.extractall(destination, filter="data")


def _safe_extract_zip(archive: Path, destination: Path):
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (root / member.filename).resolve()
            if os.path.commonpath((str(root), str(target))) != str(root):
                raise RuntimeError(f"Unsafe path in model archive: {member.filename}")
        zf.extractall(destination)


def extract_archive(archive: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        _safe_extract_zip(archive, destination)
    else:
        _safe_extract_tar(archive, destination)


def _choose_onnx(paths: list[Path], role: str) -> Path | None:
    candidates = [
        path for path in paths
        if path.suffix.lower() == ".onnx" and role in path.name.lower()
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda p: (
            0 if "int8" in p.name.lower() else 1,
            len(p.parts),
            len(p.name),
        )
    )
    return candidates[0]


def discover_transducer_files(model_dir: Path) -> dict[str, Path]:
    onnx_files = list(model_dir.rglob("*.onnx"))
    tokens_files = list(model_dir.rglob("tokens.txt"))
    if not onnx_files:
        raise RuntimeError("No .onnx files found in the downloaded Sherpa archive")
    if not tokens_files:
        raise RuntimeError("No tokens.txt found in the downloaded Sherpa archive")

    # The transducer encoder/decoder/joiner must be from the same directory.
    parents = {p.parent for p in onnx_files}
    for parent in sorted(parents, key=lambda p: (len(p.parts), str(p))):
        local = list(parent.glob("*.onnx"))
        encoder = _choose_onnx(local, "encoder")
        decoder = _choose_onnx(local, "decoder")
        joiner = _choose_onnx(local, "joiner")
        if encoder and decoder and joiner:
            tokens = next((p for p in tokens_files if p.parent == parent), None)
            if tokens is None:
                tokens = min(tokens_files, key=lambda p: len(p.parts))
            return {
                "encoder": encoder,
                "decoder": decoder,
                "joiner": joiner,
                "tokens": tokens,
            }

    raise RuntimeError(
        "This archive does not look like a supported transducer model. "
        "This add-on version currently supports Sherpa online/offline transducer "
        "archives containing encoder*.onnx, decoder*.onnx, joiner*.onnx and tokens.txt."
    )


def detect_model_type(archive_name: str, model_dir: Path, requested: str) -> str:
    if requested != "auto":
        if requested not in SUPPORTED_MODEL_TYPES:
            raise ValueError(f"Unsupported model_type: {requested}")
        return requested

    # Filename conventions in the official catalogue are useful hints, not proof.
    name = archive_name.lower()
    if any(token in name for token in ("streaming", "online")):
        return "online_transducer"
    if any(token in name for token in ("offline", "parakeet", "tdt")):
        return "offline_transducer"

    # A few release archives include README/config metadata. Only use explicit
    # declarations; don't guess from arbitrary words in a long README.
    for readme in list(model_dir.rglob("README*"))[:5]:
        try:
            text = readme.read_text(encoding="utf-8", errors="ignore")[:100_000].lower()
        except OSError:
            continue
        if "online recognizer" in text or "streaming transducer" in text:
            return "online_transducer"
        if "offline recognizer" in text or "offline transducer" in text:
            return "offline_transducer"

    raise RuntimeError(
        "Could not confidently determine whether this model is streaming or offline. "
        "Set model_type to online_transducer or offline_transducer in the add-on options."
    )


def model_directory(archive_name: str) -> Path:
    return MODEL_ROOT / safe_model_name(archive_name).removesuffix(".tar.bz2").removesuffix(".tar.gz").removesuffix(".tgz").removesuffix(".zip")


def download_and_prepare_model(archive_name: str, requested_type: str):
    if not archive_name:
        assets = get_catalogue()
        log_catalogue(assets)
        raise RuntimeError(
            "No model selected. Check the add-on log for the current official Sherpa "
            "ASR archive catalogue, then set model_archive to the exact archive filename "
            "in the add-on configuration."
        )

    assets = get_catalogue()
    asset = next((item for item in assets if item["name"] == archive_name), None)
    if asset is None:
        # Refresh once in case a new archive has just been published.
        assets = get_catalogue(force_refresh=True)
        asset = next((item for item in assets if item["name"] == archive_name), None)
    if asset is None:
        examples = ", ".join(item["name"] for item in assets[:12])
        raise ValueError(
            f"{archive_name!r} is not an archive in the official Sherpa ASR release. "
            f"Some available archives: {examples}"
        )

    model_dir = model_directory(archive_name)
    try:
        files = discover_transducer_files(model_dir)
        _LOGGER.info("Using cached Sherpa model in %s", model_dir)
    except (RuntimeError, OSError):
        archive_path = MODEL_ROOT / safe_model_name(archive_name)
        if not archive_path.is_file() or (
            asset["size"] and archive_path.stat().st_size != asset["size"]
        ):
            download_archive(asset, archive_path)

        with tempfile.TemporaryDirectory(prefix="sherpa-extract-", dir=MODEL_ROOT) as tmp:
            extraction_root = Path(tmp)
            extract_archive(archive_path, extraction_root)
            # Archives generally contain one model directory. If not, search
            # extracted content and copy the common ancestor of the discovered files.
            candidate_roots = [extraction_root] + [p for p in extraction_root.iterdir() if p.is_dir()]
            selected_root = None
            for candidate in candidate_roots:
                try:
                    discover_transducer_files(candidate)
                    selected_root = candidate
                    break
                except RuntimeError:
                    continue
            if selected_root is None:
                raise RuntimeError(
                    f"Downloaded archive {archive_name} does not contain a supported "
                    "online/offline transducer layout."
                )
            if model_dir.exists():
                shutil.rmtree(model_dir)
            shutil.copytree(selected_root, model_dir)

        files = discover_transducer_files(model_dir)

    model_type = detect_model_type(archive_name, model_dir, requested_type)
    return model_dir, files, model_type, asset


def create_recognizer(files: dict[str, Path], model_type: str, threads: int,
                      offline_model_type: str):
    paths = {key: str(value) for key, value in files.items()}
    _LOGGER.info(
        "Loading %s model: encoder=%s decoder=%s joiner=%s tokens=%s",
        model_type, files["encoder"].name, files["decoder"].name,
        files["joiner"].name, files["tokens"].name,
    )

    if model_type == "online_transducer":
        recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            encoder=paths["encoder"],
            decoder=paths["decoder"],
            joiner=paths["joiner"],
            tokens=paths["tokens"],
            num_threads=threads,
            sample_rate=RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            provider="cpu",
        )
        return recognizer, int(0.66 * RATE)

    if model_type == "offline_transducer":
        recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=paths["encoder"],
            decoder=paths["decoder"],
            joiner=paths["joiner"],
            tokens=paths["tokens"],
            num_threads=threads,
            sample_rate=RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            model_type=offline_model_type,
            provider="cpu",
        )
        return recognizer, 0

    raise ValueError(f"Unsupported model type: {model_type}")


def parse_languages(value: str, default_language: str) -> list[str]:
    languages = [item.strip() for item in (value or "").split(",") if item.strip()]
    if not languages:
        languages = [default_language] if default_language else ["auto"]
    return list(dict.fromkeys(languages))


class OnlineSession:
    def __init__(self, recognizer, tail_samples: int, language: str,
                 language_option: bool):
        self.recognizer = recognizer
        self.tail_samples = tail_samples
        self.stream = recognizer.create_stream()
        if language_option and language:
            self.stream.set_option("language", language)
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


class OfflineSession:
    def __init__(self, recognizer):
        self.recognizer = recognizer
        self.audio = []
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
            samples = np.frombuffer(pcm, dtype=np.int16).copy()
            self.audio.append(samples)
            self.audio_samples += len(samples)

    def result(self):
        if self.leftover:
            self.audio.append(np.frombuffer(self.leftover + b"\x00", dtype=np.int16).copy())
            self.audio_samples += 1
            self.leftover = b""
        if self.audio:
            samples = np.concatenate(self.audio).astype(np.float32) / 32768.0
        else:
            samples = np.zeros(0, dtype=np.float32)
        stream = self.recognizer.create_stream()
        stream.accept_waveform(RATE, samples)
        self.recognizer.decode_stream(stream)
        text = stream.result.text
        elapsed = max(time.monotonic() - self.started, 1e-6)
        audio_seconds = self.audio_samples / RATE
        rtf = elapsed / audio_seconds if audio_seconds else 0.0
        return text, audio_seconds, elapsed, rtf


class Handler(AsyncEventHandler):
    def __init__(self, info: Info, recognizer, tail_samples: int, model_type: str,
                 archive_name: str, languages: list[str], default_language: str,
                 language_option: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info_event = info.event()
        self.recognizer = recognizer
        self.tail_samples = tail_samples
        self.model_type = model_type
        self.archive_name = archive_name
        self.languages = languages
        self.default_language = default_language
        self.language_option = language_option
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
            if self.languages and "auto" not in self.languages and self.language not in self.languages:
                raise ValueError(
                    f"Language {self.language!r} is not advertised by this model. "
                    f"Configured languages: {', '.join(self.languages)}"
                )
            return True

        if AudioStart.is_type(event.type):
            self.session = (
                OfflineSession(self.recognizer)
                if self.model_type == "offline_transducer"
                else OnlineSession(self.recognizer, self.tail_samples, self.language, self.language_option)
            )
            self.got_audio = False
            return True

        if AudioChunk.is_type(event.type):
            if self.session is None:
                self.session = (
                    OfflineSession(self.recognizer)
                    if self.model_type == "offline_transducer"
                    else OnlineSession(self.recognizer, self.tail_samples, self.language, self.language_option)
                )
            chunk = self.converter.convert(AudioChunk.from_event(event))
            self.got_audio = True
            await asyncio.to_thread(self.session.accept, chunk.audio)
            return True

        if AudioStop.is_type(event.type):
            if not self.got_audio or self.session is None:
                await self.write_event(Transcript(text="").event())
                self.session = None
                return False
            text, audio_s, elapsed_s, rtf = await asyncio.to_thread(self.session.result)
            _LOGGER.info(
                "[%s | %s] %.2fs audio -> %.3fs processing, RTF %.3f: %s",
                self.archive_name, self.model_type, audio_s, elapsed_s, rtf, text,
            )
            await self.write_event(Transcript(text=text, language=self.language or None).event())
            self.session = None
            return False

        return True


async def main():
    cfg = options()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    archive_name = str(cfg.get("model_archive", "")).strip()
    requested_type = cfg.get("model_type", "auto")
    language = cfg.get("language", "nl-NL")
    languages = parse_languages(cfg.get("languages", ""), language)
    threads = int(cfg.get("num_threads", 4))
    language_option = bool(cfg.get("language_option", False))
    offline_model_type = cfg.get("offline_model_type", "nemo_transducer")

    if requested_type not in SUPPORTED_MODEL_TYPES:
        raise ValueError(f"model_type must be one of: {', '.join(SUPPORTED_MODEL_TYPES)}")
    if offline_model_type not in ("transducer", "nemo_transducer"):
        raise ValueError("offline_model_type must be transducer or nemo_transducer")

    assets = get_catalogue()
    if not archive_name:
        log_catalogue(assets)
        raise RuntimeError(
            "Set model_archive to the exact filename of a model in the official Sherpa ASR catalogue. "
            "The current list is printed above in the add-on log."
        )

    model_dir, files, model_type, asset = download_and_prepare_model(archive_name, requested_type)
    _LOGGER.info("Selected official Sherpa model: %s", archive_name)
    _LOGGER.info("Model directory: %s", model_dir)
    _LOGGER.info("Detected/selected model type: %s", model_type)

    recognizer, tail_samples = create_recognizer(files, model_type, threads, offline_model_type)

    model = AsrModel(
        name=archive_name,
        description=f"Official Sherpa-ONNX ASR model ({model_type})",
        attribution=Attribution(
            name="k2-fsa sherpa-onnx / model authors",
            url="https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models",
        ),
        installed=True,
        languages=languages,
        version=asset.get("updated_at") or archive_name,
    )
    info = Info(asr=[AsrProgram(
        name="sherpa-onnx-stt",
        description="Sherpa-ONNX ASR using official pretrained model releases",
        attribution=Attribution(
            name="k2-fsa sherpa-onnx",
            url="https://github.com/k2-fsa/sherpa-onnx",
        ),
        installed=True,
        version=ADDON_VERSION,
        supports_transcript_streaming=False,
        requires_external_vad=True,
        models=[model],
    )])

    server = AsyncServer.from_uri("tcp://0.0.0.0:10300")
    if cfg.get("zeroconf", True) and isinstance(server, AsyncTcpServer):
        from wyoming.zeroconf import HomeAssistantZeroconf
        zc = HomeAssistantZeroconf(name="Sherpa Streaming STT", port=server.port, host=server.host)
        await zc.register_server()
        _LOGGER.info("Wyoming Zeroconf discovery enabled")

    _LOGGER.info(
        "Ready: model=%s type=%s language=%s advertised=%s threads=%d",
        archive_name, model_type, language, ",".join(languages), threads,
    )
    await server.run(partial(
        Handler, info, recognizer, tail_samples, model_type, archive_name,
        languages, language, language_option,
    ))


if __name__ == "__main__":
    asyncio.run(main())
