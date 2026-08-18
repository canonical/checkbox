# Readme for Video Codec Jobs

This readme provides an overview of the different video codec scenarios

## Structure

The video-codec framework follows the same concept as the camera framework
(`units/camera`):

- A per-DUT conf file in `data/video-codec-test-confs/<platform>.json`
  (selected by `VIDEO_CODEC_JSON_CONFIG_NAME`) declares which scenarios,
  plugins and resolutions the platform tests. A platform runs a scenario
  if and only if its conf declares it.
- The resource job composes a `name` per record, and every job-id template
  is the generic `ce-oem-video-codec/{{ name }}` — no per-platform
  templates. The per-family id shapes live in the `PLATFORM_FAMILIES`
  table in `bin/codec_platforms.py`.
- Platform-specific gstreamer pipelines live in `bin/codec_<family>.py`
  modules resolved by `codec_factory()` — the per-scenario scripts carry
  no platform knowledge.

## Contributing: Adding New Platforms

1. **Create the conf file** `data/video-codec-test-confs/<platform>.json`
   with the scenario sections the platform supports (copy an existing
   conf as reference — e.g. `rzg2l.json` for a small one).
2. **Add one `PlatformFamily` entry** to `PLATFORM_FAMILIES` in
   `bin/codec_platforms.py` (or add the conf-name prefix to an existing
   family). Declare its job-id prefix, which optional fields its encoder
   ids append, and whether its decoder-performance ids need the
   golden-sample name (only when one decoder element serves several
   codecs).
3. **Add `bin/codec_<family>.py`** when the platform needs its own
   pipelines: expose `create_encoder_psnr_project(args)` (returning a
   `PipelineInterface` implementation) and, if the generic
   decoder-performance pipeline does not fit,
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

### Scenario: gst_v4l2_video_decoder_md5_checksum_comparison

#### Goal
  
The purpose of this scenario is to use MD5 checksum comparison to ensure that Gstreamer Video-related decoders, under different combinations (decoder plugin, resolution, and color space), produce MD5 checksums that match those of the Golden Sample.

Please reference [v4l2_video_decoder_md5_checksum_comparison](https://docs.google.com/document/d/1yuAdse3u64QZGCL2VQ4_PpuPIC0i1yXqHxKI6660WFg/edit#heading=h.rh805u3vq3ig) to learn the detail.
