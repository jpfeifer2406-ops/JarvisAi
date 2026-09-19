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

COMPUTER v0.5.2 TEST can load the German Victoria TTS checkpoint and voicepack
from Hugging Face on first voice use.

- Project/model: kikiri-tts/kikiri-german-victoria
- Architecture: Kokoro-compatible / StyleTTS2 Stage 2
- Language: German
- License: Apache-2.0
- Use in COMPUTER: experimental default German TTS voice
- Runtime assets: kikiri_german_victoria_ep10.pth and voices/victoria.pt

The model is downloaded at runtime and is not vendored into this repository.
Preserve the Apache-2.0 license notice in any redistributed bundle and perform a
full model/dependency review before commercial release.

## Production rule

Do not add code or assets from third-party projects to COMPUTER unless the
license is known and compatible with the intended distribution. Prefer
permissive licenses such as MIT, BSD-3-Clause, or Apache-2.0, preserve required
notices, and document every vendored asset.
