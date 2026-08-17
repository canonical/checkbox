# Readme for Video Codec Jobs

This readme provides an overview of the different video codec scenarios

## Platform notes: NVIDIA Jetson (Orin / Thor)

Jetson platforms use the conf files `orin-agx.json`, `orin-nx.json`,
`orin-nano.json` (decode-only — the Orin Nano has no NVENC) and
`thor.json`. Platform specifics, mirroring the structure the other
platforms use:

- Every codec is decoded by the single `nvv4l2decoder` element, so the
  Jetson decoder-performance jobs come from the platform-filtered
  `jetson-gst_video_decoder_performance_fakesink` template, whose job ids
  include the golden-sample name to stay unique per codec.
- Encoding uses `nvv4l2h264enc` / `nvv4l2h265enc` / `nvv4l2av1enc` through
  the `jetson-gst_encoder_psnr` template and the `JetsonProject` pipeline
  builder.
- On Ubuntu Core images the NVIDIA GStreamer stack lives in the
  `multimedia` snap: set `GST_LAUNCH_BIN=/snap/bin/gst-launch-1.0` (snap
  alias, created at pre-test setup) in the checkbox configuration. The
  `checkbox` runtime ships no `wget`, so golden samples are downloaded to
  the DUT during setup via `multimedia.wget` (into a snap-writable path)
  and moved to `VIDEO_CODEC_TESTING_DATA`.
- Golden samples come from the usual testing-data store
  (https://github.com/canonical/CodecCrafter); the VP9/AV1
  decoder-performance samples (`1080p_30fps_vp9.webm`,
  `1080p_30fps_av1.webm`) are new for Jetson and must be provisioned
  before those jobs can run.

## Usage

Before starting the testing, please read the [OQ013 - Video Codec Testing Document](https://docs.google.com/document/d/1yuAdse3u64QZGCL2VQ4_PpuPIC0i1yXqHxKI6660WFg/edit?usp=sharing) to understand the overall testing process and the scenarios that interest you.

## Scenarios

### Scenario: gst_v4l2_video_decoder_md5_checksum_comparison

#### Goal
  
The purpose of this scenario is to use MD5 checksum comparison to ensure that Gstreamer Video-related decoders, under different combinations (decoder plugin, resolution, and color space), produce MD5 checksums that match those of the Golden Sample.

Please reference [v4l2_video_decoder_md5_checksum_comparison](https://docs.google.com/document/d/1yuAdse3u64QZGCL2VQ4_PpuPIC0i1yXqHxKI6660WFg/edit#heading=h.rh805u3vq3ig) to learn the detail.
