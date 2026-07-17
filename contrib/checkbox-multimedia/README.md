# checkbox-provider-multimedia

Checkbox provider for multimedia hardware validation (VA-API codecs).

## Dependencies

```bash
sudo snap install fluster --edge
sudo apt install gstreamer1.0-tools gstreamer1.0-vaapi \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly libva-utils vainfo
```

## How to run

```bash
./manage.py validate
./manage.py test
./manage.py develop
checkbox-cli run com.canonical.contrib::multimedia-codecs-vaapi
```
