# checkbox-provider-multimedia

Checkbox provider for multimedia hardware validation.

## How to run

```bash
cd checkbox/contrib/checkbox-multimedia
rm /var/tmp/checkbox-providers-develop/checkbox-provider-multimedia.provider && ./manage.py develop && checkbox-cli run com.canonical.contrib::multimedia-codecs-vaapi
```
