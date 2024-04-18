# Readme for Gstreamer-Related Jobs

This readme provides an overview of the different gstreamer tests available in this project

## Usage

Before starting the testing, please read the [OQ013 - Gstreamer Testing Document](https://docs.google.com/document/d/1yuAdse3u64QZGCL2VQ4_PpuPIC0i1yXqHxKI6660WFg/edit?usp=sharing) to understand the overall testing process and the scenarios that interest you.

## Scenarios

### Scenario: gst_v4l2_video_decoder_md5_checksum_comparison

#### Goal
  
  The purpose of this scenario is to use MD5 checksum comparison to ensure that Gstreamer Video-related decoders, under different combinations (decoder plugin, resolution, and color space), produce MD5 checksums that match those of the Golden Sample.

  Please reference [v4l2_video_decoder_md5_checksum_comparison](https://docs.google.com/document/d/1yuAdse3u64QZGCL2VQ4_PpuPIC0i1yXqHxKI6660WFg/edit#heading=h.rh805u3vq3ig) to learn the detail.
