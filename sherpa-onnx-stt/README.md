# Sherpa ONNX STT

Run local speech-to-text in Home Assistant using [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) and the Wyoming protocol.

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg

## Features

- Runs speech recognition locally using Sherpa-ONNX models
- Supports online and offline transducer models
- Downloads and prepares the selected model archive on first startup
- Stores model files in the add-on configuration directory for reuse
- Provides a Wyoming speech-to-text service on port `10300` (or a custom port if you already have `Whisper` running on the same machine)
- Optionally advertises the service using Zeroconf

## Installation

1. Add this repository (`https://github.com/h3llrais3r/hassio-addons`) to Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Install **Sherpa ONNX STT**
3. Configure the model and language options
4. Start the add-on and wait for the model download to finish
5. Add the **Wyoming Protocol** integration in Home Assistant and connect it to the add-on host on port `10300` (or your configured port if you have already `Whisper` running on the same machine)

## Configuration

Example using the default offline Parakeet model:

```yaml
language: en
languages: "bg,hr,cs,da,nl,en,et,fi,fr,de,el,hu,it,lv,lt,mt,pl,pt,ro,sk,sl,es,sv,ru,uk"
model_archive: sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
model_type: offline_transducer
num_threads: 4
language_option: false
offline_model_type: nemo_transducer
zeroconf: true
```

| Option | Description |
| --- | --- |
| `model_archive` | Exact filename of a model archive published in the [Sherpa-ONNX ASR model releases](https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models). The add-on downloads it on startup and stores the extracted files under `/config/models`. |
| `model_type` | Select `auto`, `online_transducer`, or `offline_transducer`. `auto` detects the model type from the archive and its files. |
| `num_threads` | Number of CPU threads used by the recognizer (1–8). |
| `language` | Default language tag used when a Wyoming request does not specify a language. It does not force an offline model to recognize that language. |
| `languages` | Comma-separated language tags advertised to Home Assistant and accepted from requests. This setting does not change the languages supported by the model. |
| `language_option` | For supported online models, pass the request language (or the default) as a language hint. Has no effect on offline models. |
| `offline_model_type` | Offline recognizer type: `transducer` or `nemo_transducer`. Select the type appropriate for your model. |
| `zeroconf` | Enable Zeroconf service advertisement for discovery on the local network. |

This add-on currently supports Sherpa-ONNX transducer archives containing `encoder*.onnx`, `decoder*.onnx`, `joiner*.onnx`, and `tokens.txt`. Recognition languages depend on the selected model; the `languages` option only controls advertised and accepted language tags.

## Support

For model details and available archives, see the [Sherpa-ONNX ASR model releases](https://github.com/k2-fsa/sherpa-onnx/releases/tag/asr-models). For add-on issues, use the [repository issue tracker](https://github.com/h3llrais3r/hassio-addons/issues).
