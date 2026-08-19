
## <a id='top'>environ keys for video-codec tests</a>

- VIDEO_CODEC_JSON_CONFIG_NAME
    - Affected Test Cases:
        - [video_codec_resource](#video_codec_resource)
- VIDEO_CODEC_TESTING_DATA
    - Affected Test Cases:
        - [video_codec_resource](#video_codec_resource)
        - [ce-oem-video-codec/gst_encoder_psnr](#ce-oem-video-codec/gst_encoder_psnr)
        - [ce-oem-video-codec/gst_transform_rotate_and_flip](#ce-oem-video-codec/gst_transform_rotate_and_flip)
        - [ce-oem-video-codec/gst_transform_resize](#ce-oem-video-codec/gst_transform_resize)
- PLAINBOX_PROVIDER_DATA
    - Affected Test Cases:
        - [video_codec_resource](#video_codec_resource)
- PLAINBOX_SESSION_SHARE
    - Affected Test Cases:
        - [ce-oem-video-codec/gst_encoder_psnr](#ce-oem-video-codec/gst_encoder_psnr)
        - [ce-oem-video-codec/gst_transform_rotate_and_flip](#ce-oem-video-codec/gst_transform_rotate_and_flip)
        - [ce-oem-video-codec/gst_transform_resize](#ce-oem-video-codec/gst_transform_resize)
- GST_LAUNCH_BIN
    - Affected Test Cases:
        - [ce-oem-video-codec/readiness](#ce-oem-video-codec/readiness)
        - [ce-oem-video-codec/gst_video_decoder_md5_checksum_comparison](#ce-oem-video-codec/gst_video_decoder_md5_checksum_comparison)
        - [ce-oem-video-codec/gst_v4l2_audio_video_synchronization](#ce-oem-video-codec/gst_v4l2_audio_video_synchronization)
        - [ce-oem-video-codec/gst_video_decoder_performance_fakesink](#ce-oem-video-codec/gst_video_decoder_performance_fakesink)
        - [ce-oem-video-codec/gst_encoder_psnr](#ce-oem-video-codec/gst_encoder_psnr)
        - [ce-oem-video-codec/gst_transform_rotate_and_flip](#ce-oem-video-codec/gst_transform_rotate_and_flip)
        - [ce-oem-video-codec/gst_transform_resize](#ce-oem-video-codec/gst_transform_resize)
- GST_DISCOVERER
    - Affected Test Cases:
        - [ce-oem-video-codec/readiness](#ce-oem-video-codec/readiness)
        - [ce-oem-video-codec/gst_encoder_psnr](#ce-oem-video-codec/gst_encoder_psnr)

## Detailed test cases contains environ variable
### <a id='video_codec_resource'>video_codec_resource</a>
- **summary:**
Generates mappings for all Video Codec Scenarios

- **description:**
```
Generate resource for all Video Codec scenarios.
```

- **file:**
[source file](jobs.pxu#L1)

- **environ:**
VIDEO_CODEC_JSON_CONFIG_NAME VIDEO_CODEC_TESTING_DATA PLAINBOX_PROVIDER_DATA

- **command:**
```
gst_resources_generator.py "$VIDEO_CODEC_JSON_CONFIG_NAME" -gtdp "$VIDEO_CODEC_TESTING_DATA"
```
[Back to top](#top)

### <a id='ce-oem-video-codec/readiness'>ce-oem-video-codec/readiness</a>
- **summary:**
Verify installation of the GStreamer tools

- **description:**
```
Checks if the system has the necessary GStreamer binaries installed to proceed with video codec testing.
```

- **file:**
[source file](jobs.pxu#L11)

- **environ:**
GST_LAUNCH_BIN GST_DISCOVERER

- **command:**
```
for tool in "${GST_LAUNCH_BIN:-gst-launch-1.0}" "${GST_DISCOVERER:-gst-discoverer-1.0}"; do
    command -v "$tool" || { echo "Error: $tool not found"; exit 1; }
done
```
[Back to top](#top)

### <a id='ce-oem-video-codec/gst_video_decoder_md5_checksum_comparison'>ce-oem-video-codec/gst_video_decoder_md5_checksum_comparison</a>
- **summary:**
MD5 checksum comparison {{ width }}x{{ height }}-{{ decoder_plugin }}-{{ color_space }}

- **template_summary:**
To check if the MD5 checksum is same as golden reference under specific decoder

- **description:**
```
Compare the MD5 checksum to golden reference by decoding the {{ width }}x{{ height }}-{{ decoder_plugin }}-{{ color_space }} video via gstreamer
```

- **file:**
[source file](jobs.pxu#L23)

- **environ:**
GST_LAUNCH_BIN

- **command:**
```
   gst_video_decoder_md5_checksum_comparison.py -dp {{decoder_plugin}} -cs {{color_space}} -gp {{golden_sample_file}} -gmp {{golden_md5_checkum_file}} -p "{{ platform }}"
```
[Back to top](#top)

### <a id='ce-oem-video-codec/gst_v4l2_audio_video_synchronization'>ce-oem-video-codec/gst_v4l2_audio_video_synchronization</a>
- **summary:**
AV-Sync test of decoder {{ decoder_plugin }} with {{ golden_sample_file_name }} file

- **template_summary:**
To check if the relative timing of audio and video is synchronized

- **description:**
```
To check if the relative timing of audio and video of {{ golden_sample_file_name }} file is synchronized under a specific {{ decoder_plugin }} decoder
```

- **file:**
[source file](jobs.pxu#L44)

- **environ:**
GST_LAUNCH_BIN

- **command:**
```
   gst_v4l2_audio_video_synchronization.py -dp {{decoder_plugin}} -gp {{golden_sample_file}} -vs {{video_sink}} -cp "{{capssetter_pipeline}}"
```
[Back to top](#top)

### <a id='ce-oem-video-codec/gst_video_decoder_performance_fakesink'>ce-oem-video-codec/gst_video_decoder_performance_fakesink</a>
- **summary:**
Performance test of decoder - {{ name }}

- **template_summary:**
To check if the performance of decoder doesn't violate Pass Criteria

- **description:**
```
Test if while the sink is fakesink, the decoder's performance, {{ decoder_plugin }}, doesn't violate the Pass Criteria. (1) There are no frame losses (2) Average FPS not fall below the specification's definition
```

- **file:**
[source file](jobs.pxu#L73)

- **environ:**
GST_LAUNCH_BIN

- **command:**
```
   gst_video_decoder_performance.py -gp {{golden_sample_file}} -dp {{decoder_plugin}} -mf {{minimum_fps}} -p "{{ platform }}"
```
[Back to top](#top)

### <a id='ce-oem-video-codec/gst_encoder_psnr'>ce-oem-video-codec/gst_encoder_psnr</a>
- **summary:**
Encoder PSNR - {{ name }}

- **template_summary:**
Verify the PSNR ratio meets requirement for specific encoder

- **description:**
```
Test if the PSNR value of an artifact which is generated from {{ encoder_plugin }} encoder reaches the acceptable threshold
```

- **file:**
[source file](jobs.pxu#L95)

- **environ:**
GST_LAUNCH_BIN, PLAINBOX_SESSION_SHARE, VIDEO_CODEC_TESTING_DATA, GST_DISCOVERER

- **command:**
```
   gst_encoder_psnr.py -p "{{ platform }}" -ep "{{ encoder_plugin }}" -cs "{{ color_space }}" -wi {{ width }} -hi {{ height }} -f {{ framerate }} -m "{{ mux }}"
```
[Back to top](#top)

### <a id='ce-oem-video-codec/gst_transform_rotate_and_flip'>ce-oem-video-codec/gst_transform_rotate_and_flip</a>
- **summary:**
Perform {{ action }} - {{ width }}x{{ height }}_{{ framerate }}fps file

- **template_summary:**
Check if the rotation or flip operations are functional

- **file:**
[source file](jobs.pxu#L117)

- **environ:**
GST_LAUNCH_BIN, PLAINBOX_SESSION_SHARE, VIDEO_CODEC_TESTING_DATA

- **command:**
```
   gst_transform_rotate_and_flip.py -p "{{ platform }}" -ep "{{ encoder_plugin }}" -wi "{{ width }}" -hi "{{ height }}" -f "{{ framerate }}" -a "{{ action }}"
```
[Back to top](#top)

### <a id='ce-oem-video-codec/gst_transform_resize'>ce-oem-video-codec/gst_transform_resize</a>
- **summary:**
Perform resize - from {{ width_from }}x{{ height_from }} to {{ width_to }}x{{ height_to }} file

- **template_summary:**
Check if the resize (scale up or down) are functional

- **file:**
[source file](jobs.pxu#L138)

- **environ:**
GST_LAUNCH_BIN, PLAINBOX_SESSION_SHARE, VIDEO_CODEC_TESTING_DATA

- **command:**
```
   gst_transform_resize.py -p "{{ platform }}" -ep "{{ encoder_plugin }}" -wf "{{ width_from }}" -hf "{{ height_from }}" -wt "{{ width_to }}" -ht "{{ height_to }}" -f "{{ framerate }}"
```
[Back to top](#top)
