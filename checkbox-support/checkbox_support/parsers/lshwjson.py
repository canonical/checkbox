import sys
import json

class LshwJsonParser:

    def __init__(self, stream_or_string):
        self.stream_or_string = stream_or_string

    def _parse_lshw(self, lshw, result):
        if 'children' in lshw.keys():
            for child in lshw['children']:
                self._parse_lshw(child, result)
            del lshw['children']

        result.addHardware(lshw)

    def run(self, result):
        try:
            lshw = json.loads(self.stream_or_string)
        except:
            print('not valid json')

        self._parse_lshw(lshw, result)
