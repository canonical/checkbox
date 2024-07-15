
## <a id='top'>environ keys for video-codec tests</a>

- VIDEO_CODEC_JSON_CONFIG_NAME
    - Affected Test Cases:
        - [video_codec_resource](#video_codec_resource)
- VIDEO_CODEC_TESTING_DATA
    - Affected Test Cases:
        - [video_codec_resource](#video_codec_resource)
- PLAINBOX_PROVIDER_DATA
    - Affected Test Cases:
        - [video_codec_resource](#video_codec_resource)
- GST_LAUNCH_BIN
    - Affected Test Cases:
        - [ce-oem-video-codec/gst_v4l2_video_decoder_md5_checksum_comparison](#ce-oem-video-codec/gst_v4l2_video_decoder_md5_checksum_comparison)

## Detailed test cases contains environ variable
### <a id='video_codec_resource'>video_codec_resource</a>
- **summary:**
Generates mappings for all Vedio Codec Scenarios

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

### <a id='ce-oem-video-codec/gst_v4l2_video_decoder_md5_checksum_comparison'>ce-oem-video-codec/gst_v4l2_video_decoder_md5_checksum_comparison</a>
- **summary:**
MD5 checksum comparison {{ width }}x{{ height }}-{{ decoder_plugin }}-{{ color_space }}

- **template_summary:**
To check if the MD5 checksum is same as golden reference under specific decoder

- **description:**
```
Compare the MD5 checksum to golden reference by decoding the {{ width }}x{{ height }}-{{ decoder_plugin }}-{{ color_space }} video via gstreamer
```

- **file:**
[source file](jobs.pxu#L11)

- **environ:**
GST_LAUNCH_BIN

- **command:**
```
   gst_v4l2_video_decoder_md5_checksum_comparison.py -dp {{decoder_plugin}} -cs {{color_space}} -gp {{golden_sample_file}} -gmp {{golden_md5_checkum_file}}
```
[Back to top](#top)
