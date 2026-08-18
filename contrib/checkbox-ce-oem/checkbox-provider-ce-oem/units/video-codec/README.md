# Readme for Video Codec Jobs

This readme provides an overview of the different video codec scenarios

## Structure

The video-codec framework follows the same concept as the camera framework
(`units/camera`):

- A per-DUT conf file in `data/video-codec-test-confs/` (selected by
  `VIDEO_CODEC_JSON_CONFIG_NAME`) declares which scenarios, plugins and
  resolutions the platform tests. A platform runs a scenario if and only
  if its conf declares it. Conf files follow one naming rule:
  `<family>[-<board>].json` — the file name starts with its platform
  family (e.g. `genio-1200.json`, `imx-8mp.json`, `rzg2l.json`,
  `dragonwing.json`).
- The resource job composes a `name` per record, and every job-id template
  is the generic `ce-oem-video-codec/{{ name }}` — no per-platform
  templates. The per-family id shapes live in the `PLATFORM_FAMILIES`
  table in `bin/codec_platforms.py`.
- Platform-specific gstreamer pipelines live in `bin/codec_<family>.py`
  modules resolved by `codec_factory()` — the per-scenario scripts carry
  no platform knowledge.

## Contributing: Adding New Platforms

1. **Create the conf file** `data/video-codec-test-confs/<family>[-<board>].json`
   with the scenario sections the platform supports (copy an existing
   conf as reference — e.g. `rzg2l.json` for a small one). The file name
   must start with the platform family name.
2. **Add one `PlatformFamily` entry** to `PLATFORM_FAMILIES` in
   `bin/codec_platforms.py`, keyed by the family name (boards of an
   existing family need no new entry — their conf names already match).
   Declare its job-id prefix, which optional fields its encoder ids
   append, and whether its decoder-performance ids need the
   golden-sample name (only when one decoder element serves several
   codecs).
3. **Add `bin/codec_<family>.py`** when the platform needs its own
   pipelines: expose `create_encoder_psnr_project(args)` returning a
   project class that inherits `BaseCodecProject` (`bin/codec_base.py`) —
   the basic class implements the `PipelineInterface` ABC with the shared
   defaults, so the platform class only fills `self._pipeline_builders`
   with its codec → builder mapping and overrides what differs, the same
   way the camera platform classes inherit their base camera class. If
   the generic decoder-performance pipeline does not fit, also expose
   `build_decoder_performance_command(...)`. Platforms that only use the
   generic pipelines can skip the module entirely.
4. **Provide the golden samples** the conf references in the testing-data
   store (https://github.com/canonical/CodecCrafter) so the download
   manager can fetch them.
5. **Validate**: run the resource generator against the new conf, check
   the generated job names, and run the relevant unit tests
   (`tests/test_gst_resources_generator.py`, `tests/test_codec_platforms.py`).

## Usage

Before starting the testing, please read the [OQ013 - Video Codec Testing Document](https://docs.google.com/document/d/1yuAdse3u64QZGCL2VQ4_PpuPIC0i1yXqHxKI6660WFg/edit?usp=sharing) to understand the overall testing process and the scenarios that interest you.

## Scenarios

### Scenario: gst_video_decoder_md5_checksum_comparison

#### Goal
  
The purpose of this scenario is to use MD5 checksum comparison to ensure that Gstreamer Video-related decoders, under different combinations (decoder plugin, resolution, and color space), produce MD5 checksums that match those of the Golden Sample.

Please reference [v4l2_video_decoder_md5_checksum_comparison](https://docs.google.com/document/d/1yuAdse3u64QZGCL2VQ4_PpuPIC0i1yXqHxKI6660WFg/edit#heading=h.rh805u3vq3ig) to learn the detail.
