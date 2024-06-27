
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

## Detailed test cases contains environ variable
### <a id='video_codec_resource'>video_codec_resource</a>
- **summary:**
Generates mappings for all Vedio Codec Scenarios

- **description:**
```
Generate resource for all Video Codec scenarios.
```

- **file:**
[source file](jobs.pxu:1-9)

- **environ:**
VIDEO_CODEC_JSON_CONFIG_NAME VIDEO_CODEC_TESTING_DATA PLAINBOX_PROVIDER_DATA

- **command:**
```
gst_resources_generator.py "$VIDEO_CODEC_JSON_CONFIG_NAME" -gtdp "$VIDEO_CODEC_TESTING_DATA"
```
[Back to top](#top)
