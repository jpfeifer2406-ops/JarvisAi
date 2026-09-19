# Third-party notices for COMPUTER experimental branches

This file records external components introduced by COMPUTER-specific work.
It is not a complete dependency/license inventory for the full upstream project.

## Globe.GL

The experimental News Globe UI loads Globe.GL 2.46.2 from jsDelivr.

- Project: Globe.GL by Vasco Asturiano / contributors
- Upstream: https://github.com/vasturiano/globe.gl
- License: MIT
- Use in COMPUTER: WebGL globe rendering and camera/marker APIs

The COMPUTER news cockpit layout, styling, state handling, and news workflow are
project-specific code. The integration follows Globe.GL's documented public API.

## Earth texture

The experimental globe currently loads the earth-blue-marble.jpg example
texture distributed with three-globe. The imagery is based on NASA Blue Marble
Earth imagery.

Before any commercial release, the image asset should be vendored or replaced
with an explicitly documented production asset and its attribution/usage terms
should be reviewed as part of the full license inventory.

NASA media guidance:
https://www.nasa.gov/nasa-brand-center/images-and-media/


## Kikiri German — Victoria

COMPUTER v0.6.0 TEST can load the German Victoria TTS checkpoint and voicepack
from Hugging Face on first voice use.

- Project/model: kikiri-tts/kikiri-german-victoria
- Architecture: Kokoro-compatible / StyleTTS2 Stage 2
- Language: German
- License: Apache-2.0
- Use in COMPUTER: experimental default German TTS voice
- Runtime assets: kikiri_german_victoria_ep10.pth and voices/victoria.pt

The model is downloaded at runtime and is not vendored into this repository.
v0.6.0 pins the semidark Kokoro and Misaki forks required by the model's
reference German DEG2P inference path. Those forks are Apache-2.0 projects.
The Kokoro vocabulary/config used for Victoria inference is included in
`jarvis/tts_assets/kikiri_config.json` from the kikiri-tts training repository.

Preserve applicable Apache-2.0 notices in any redistributed bundle and perform a
full model/dependency review before commercial release.

## COMPUTER wake word

v0.6.0 TEST switches the user-facing wake word from the temporary Hey Jarvis
model to a community openWakeWord model reacting to "Computer" / "Hey Computer".

- Collection: fwartner/home-assistant-wakewords-collection
- Asset: en/computer/computer_v2.onnx
- Repository license: MIT
- Runtime use: downloaded on first start into jarvis/data/wake/
- Inference: openWakeWord ONNX on CPU

The collection documents training examples originating in other wake-word data
projects. Treat this model as an experimental development dependency until the
underlying training-data terms have been reviewed for the intended commercial
distribution. Do not equate the repository's MIT license with a completed
commercial model-data clearance.

## Optional external integrations

v0.6.0 exposes setup/status surfaces for KDE Connect and Google Drive OAuth.
Neither KDE Connect nor Google Drive software/assets are bundled by COMPUTER.
Their own terms apply when the user installs or connects those services.

## Production rule

Do not add code or assets from third-party projects to COMPUTER unless the
license is known and compatible with the intended distribution. Prefer
permissive licenses such as MIT, BSD-3-Clause, or Apache-2.0, preserve required
notices, and document every vendored asset.
