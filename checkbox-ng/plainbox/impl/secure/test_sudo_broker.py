# This file is part of Checkbox.
#
# Copyright 2017 Canonical Ltd.
# Written by:
#   Maciej Kisielewski <maciej.kisielewski@canonical.com>
#
# Checkbox is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# Checkbox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
from Crypto.PublicKey import RSA

from unittest import TestCase
from unittest.mock import patch

from plainbox.impl.secure.sudo_broker import SudoBroker
from plainbox.impl.secure.sudo_broker import SudoProvider
from plainbox.impl.secure.sudo_broker import EphemeralKey


class SudoBrokerTests(TestCase):

    def test_smoke(self):
        with patch('Crypto.PublicKey.RSA.generate',
                   return_value=MASTER_TEST_KEY):
            sb = SudoBroker()
        pubkey = RSA.importKey(sb.master_public)
        ciphertext = pubkey.encrypt(b'foobar', '_')
        self.assertEqual('foobar', sb.decrypt_password(ciphertext))

    def test_public_key_same_after_export(self):
        with patch('Crypto.PublicKey.RSA.generate',
                   return_value=MASTER_TEST_KEY):
            orig_sb = SudoBroker()
        exported = orig_sb.export_key('test_pass')
        restored_sb = SudoBroker(exported, 'test_pass')
        self.assertEqual(orig_sb.master_public, restored_sb.master_public)


class IntegrationTests(TestCase):
    def test_smoke(self):
        with patch('Crypto.PublicKey.RSA.generate',
                   return_value=MASTER_TEST_KEY):
            broker = SudoBroker()
        provider = SudoProvider(broker.master_public)
        with patch('getpass.getpass', return_value='burnafterreading'):
            provider.ask_for_password()
        self.assertEqual(
            'burnafterreading',
            broker.decrypt_password(provider.encrypted_password))

    def test_works_from_exported_master(self):
        with patch('Crypto.PublicKey.RSA.generate',
                   return_value=MASTER_TEST_KEY):
            original_broker = SudoBroker()
        provider = SudoProvider(original_broker.master_public)
        with patch('getpass.getpass', return_value='burnafterreading'):
            provider.ask_for_password()
        # get passphrase to encrypt master key before exporting
        with patch('Crypto.PublicKey.RSA.generate',
                   return_value=EPHEMERAL_TEST_KEY):
            temp_key = EphemeralKey()
        orig_master_passphrase = temp_key.decrypt(
            provider.get_master_passphrase(temp_key.public_key))
        exported = original_broker.export_key(orig_master_passphrase)
        # at this point we've got our exported (and encrypted) key
        # and this should be everything needed to decrypt the pass from
        # the provider.
        # first, let's get master passphrase using a ephemeral key
        with patch('Crypto.PublicKey.RSA.generate',
                   return_value=EPHEMERAL_TEST_KEY2):
            new_temp_key = EphemeralKey()
        new_master_passphrase = new_temp_key.decrypt(
            provider.get_master_passphrase(new_temp_key.public_key))
        self.assertEqual(orig_master_passphrase, new_master_passphrase)
        new_broker = SudoBroker(exported, new_master_passphrase)
        # new_broker should be functionally the same ads original_broker
        self.assertEqual(
            'burnafterreading',
            new_broker.decrypt_password(provider.encrypted_password))

# following keys could be a set of real, generated keys, but it takes a while
# to gather entropy, so let's use prebaked ones. I promise they've been picked
# randomly! https://xkcd.com/221/

MASTER_TEST_KEY = RSA.importKey(
    b'-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAnkKF6V0WEIFxgFMNbGrGbnqeBuSKHcXcWOS4+6qQttPU5XG2\nAAmjP7pGj/kGGJhc/m9p6Revkhyl0dpiB2aKzX+LsTD0Qle8CwwN3jeVrv8ZUV0i\nNbyhUSE/7fVNSoHJtZ4VrUD+TB+G7qSlqq5hFJpMb23TFHpahjcpDrbGBl9qG7Q+\nz8jrdXhI1jxVX8brsZWwlq3fWUEa1HM5kZp2m8MBeIMD5HbLKQcwWNUW8JnriPZr\n+UhD/oXr2Zt6tWOLY1PY4JQEaoH4NVgEikjHJ8Ejv+wqiujmiEXyu8dsgfVChozf\nqRJ3wlZC8aDXnMflu5GzIO62JBmM1Ev+IeCekwIDAQABAoIBAGvkQDT7IBq6lK1+\ncW1TUdppv6hFUB/CD1mO/Mmd27C4s7CEmCZoa6H7lTV7+Pr1jJhtTk/5tNkwrJ9n\neWNANiqo5Iw1KqC7/VeurRms3WADS7hbfQITigqsV1Ab5sh/uQsXLgICiBtPdwbk\nuoik/0wzcR6aScfxLhvIKTZ9xnz6pnrTESANzlWNRkcIEwVspe4vCW/J4ZIGpaBV\n1YfLeRiiWWe6jHDU2wGTa0070ABXvEPafGNclxOf2tbrncfgac+dP0ipv3mqVxBa\ndtai+oDcVy7fCTw6Fr+Vjg+3UIzOMqbbqBKnaNt+vXrd6SnZggbLRzN1Msvg70Oa\n8+n4tTECgYEAvSZYkig+GDPJCQ+ADAZ+/rzcFnVQZtBiMfS4NQZs8bjAsIOoE4Qn\nSrMi+UES8MlbOTIlKu03U9tVBsEnIxORZLNm8aNRhOq7vsJrk90Zp4Qvpbh0ybBt\n7pOwgT7oH8ZgdqPDJzoAY9UJMnHORptJj0CkvUg7XWUf4fJ5jZI72XsCgYEA1jFb\nZlIp27YvLyiDCNE8Q3WJNHfaoqqGr06gnxspNIgvHfSWEPcEzcf6tIlVQ9mKFdmp\n5R0uW5v/Z4AdXEsWoRkAzx4VfW8c/GrRlWpHWSTMWphZCeQvSMgCnU60lqyz1nCW\nGfbOTxw2gDQIYVL6c2zaAZ3vEQawxFYbNd2ph8kCgYASkohR2Ze3QqZzuEznYV/o\n3Vxy7BP39HAf3ZqUwkvCNFTfQB4pxGkjQZGmjcgxUmQdqpnRrDcpibjAkAiqvgoh\nrCfohBPGDFJg+bAcdbJGK4mOKR12jFdO/LtxBV8/d3gTTiMkX+KX6twbUudhMXA4\nm61RVJ1Xn01RH0DmMLylrwKBgQDOlLv6a7RDW+sWKJR4pJTi2zGBkTclPCK6YbM4\nwRF0wQPweD1kD1pqvj1mci3ySpWLjWr2trZHVKV4RXAL27/vkBXfrLw9RjVGnh+V\nY/N8XqlZlyYJDDMulvkujwJNcDPi1qNuV0OTuTo3W/fZJha3zHxWouQ4H6PNON71\njNw9QQKBgFoXsK1DMIAnwfK4EgrYsjn78LlBv2AvaTbf5KCVtmnhuozplbKOB0CQ\n1z5hXy8ZEmt+j1PgcanNIAJL8qDBXSZ13Qmjj3I2rHKbnHCL4l+B9eFcJjX2z9jE\n18Fb358rzV6Uq/g+U2Im1gs7C3DTTH2S4wMFpyE5Hh+lup/FufXf\n-----END RSA PRIVATE KEY-----')
EPHEMERAL_TEST_KEY = RSA.importKey(
    b'-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEArIwxAcO8ZQFDCG4cD4Vibga5Qo7Kbro/GPMFhf0LiG6R2xdc\npACowcIOElaDLXQOKcNqaUvfGcMrc2MpQK4c7G2COXDzrjTmtbJFdr7UK2we256F\nzvZf9nStJBMDausJcNDPSwchv/VMTKydBGcsUwA8XtS+GOWqQ6gOzl9nep2AQAUl\nVCdlUmtFodXRiRzQJAiCfLODJTV09H4eFrvA+75HsY/qflkbE8/5Xzm02CaBS7+Y\nkHbsxNv+uktSekNVyE0zSWsQtC9lmxkzvAWQbh8qE7Un/i7Dh90af9stpU0sunb6\nOnfDYEIr/jbl/xASOHA94iYBE7PzzfEO6g03HQIDAQABAoIBAGdPPNxonHkBS2hV\nvPlSDIACCJQgOHYZj0PZ5dm2i1wxj6TVFQOg3Wm9TX2PTNU/ImfA+Ap5gefD4lUg\n7wcp+Glam9jWlyAbznLFfS++y/v/rW4jOMyU2RoP+8aYl7hBZ5KjgynR6FQtg3R4\n+T40o+ZCQuMoj3UKtWnyyoKnvqY7gDjQJjr4y/AGNI+e6EyTblflbmAlnzL6ByNT\ngVVOiMugi+QU/Y6kTvl682DlVxgDCTK+xhizIUsolro/IrjxcppV9Nb7TjIZTnt4\n1gGAku4So1/6JgvnWwToB4QKywE4fu9hd1Ddgfp0arUM4gvekhFfLNtaBxw4n5Gy\nCEOnj+ECgYEAvp7l/d9owKD9PuinrrRcHRfR4ShsqomJZN8PsFH3jVRbgTAmRtHX\niQIpTqnqm0G4PzDSpuqlWoAPTPBeNY3R7Ak69cCnPOAUbofoI0br3TqNiLaQRBEe\ndQJBS0sSAiFExRl62fTUirdFuIPDM3qPQcEaFVoSrHYJmqBGL648mikCgYEA57pr\neRdxbKbszkIa/QBFN8dg/VJzM4zpv2XI5qfBJ4LrmI1R6C31aKsSoQBYQNxL8k21\noir0dLTBGGhijcwCsEsJPhHSn31JG0Cuqd6z2wvrBwZ0Zk9s3WyvqNgJcgCU4ZQa\nh8tsIErx4zG/81zJbZ6cNNHOK/0Rw3lMNQ99u9UCgYA0YYO/3JlzfYm5tMMHTgaV\n9Aq3fZ1Gy56WunkcMZn+GzU97dZG1bkNrCtfs2+FlGyl6KuqNIaVtOT/dnnc64jI\n/MxX5cXPA6B5sx0GPKHp3AIylEBWhAHDk4gPwaREM5IrO1I3/IA/Uhd1mbeVONOO\n9RpOzb6d553CANLonU+H6QKBgQDcRL/UIwyWEzYV+ZBd3dvt4X+4TJ9k6RVn8gC9\n/8gDHteD8xFgeg9EpxjWIdXCEaW/dU6qD9q+9PJ3mQHVd482tJzce2SSZi0P0rQ0\nlJSyKuoFi4Upm2YIND/lZzXTP+pFYtq1KhBlwdeb9rZXRmPR52rkampoNe6kuLBP\n36HM4QKBgQC6HF4F9q/TNNY9iyHpKZRHMYE6ON2EcGM9OwMZSjUac+3nu4Z3tz2u\ntx0jrkzQef7D1M7ZzBNYunthun3L7ufpE5TUScWaC/OoIVj6EO7QKJLWOk6DR7VW\nLPj5H0Lwgcm5uQ0AKIjhqUOnwVP0rgYphRNCt4yQ/x9+H+c7cbX96g==\n-----END RSA PRIVATE KEY-----')
EPHEMERAL_TEST_KEY2 = RSA.importKey(
    b'-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAwZ84V2IIF4qkHrU3zh2hQNLxHJzDwN3te6oxadrVR3KQlnjD\nMwSjlgKJpHbM44JecFLTGEucQHcwWi/gi1MyEcJel152zdDpVfVrrb5FhnKFe/AR\nIUOJxdXHknouD6Fgn+cMKwTViAGTQCOHuC6IizIRMco7oYNtNUkIB/PqfcbA4tBD\nUEj9GWXukLvEoCwwELODJshlrGMmhqIbgGgVtCoJ+9jOzIciK76enBv3wk14H7MQ\nkxvgRhYp8o9V/ajXgDHQpZONmgzoYuphJ/YluS9z0mmhu2ezZk1k1LSf5YEDX5hA\nuTwpAAwq3xvMP4ctFiB69/BXZMEDtrBsaQFc0QIDAQABAoIBABz1fW3EYcVznPxi\nykfvspCJfDp1T+nmx4A5gk58xm17OxjmUvusc/MZyhBpHFfixdEy8hOuK16Q9RBo\nHMN53AE/+vnUzRwXZO7QWBySWr+zHTfePhGlklOel8zWrVD1KAiCfBVrEazX33g2\nWDQ58X4wLNYvkx+jEpBnreXSm33YG1kj6A75SVpDownDMSMm3g00GZKv9kZAlc8L\n96cZ9I+4cpMLDaUGVyeWRwtKD9f9IFRdHYHeCwZ/6OmKV0skhUkbVH0TroMHtx7r\nKP/f851d32LOkwI1Mgc26jJzf73ouDuomR6Q4O0GBADTyZN6DJDgycerFxvM1zFT\nZXWR2GECgYEAyrQYJfz4dMkXke5ztNADZ0q6B2jkZ9VPhApkRtPtZq/9sVYnCiRK\nuEbzGFcU/O7Nd9fEjG3/JCRgjkIqLoXQa1wjhBWAN/jR1njXW2hRnS28tMjo/Q3w\n8fqb7Z7KBkOaw11Y8rUzHif6fkrn9fezEqyMgYjIN1icKEZ6uwJzPL0CgYEA9IfZ\nq3vq7ajr+IQ9pMa0bVyP2G/dYorK0Y7Xvy10r36wOuMUUPTP0GETOcH+snr9aD2N\nNQljOlC/fuweTYIWkep6Rx6rqQd/28h6+IGdptu+4lRoTpM8qjfMzK6wnXYCtseR\nB/BykZxkmGT8+wU9WqLlVo5RXrSMaWgZGa/pA6UCgYBHTum7221QMDnhdYAw2IiJ\n+sjMuIK5YFoTulAidoVqfXkCvKsJL1E12IfGRUQ14pBXm4kiWcPK5B0vjmkmap6y\nVfyMh7/OcPLovyQLnPwxDhj3hEIqW5AqoB3gjt7FK10zYxBaeZIdBrVhXlqRtezC\nIf9fxk2g4sQ0iu68ARWnBQKBgHSSyv9IbP/ttsjb6jNCk0NLjDvHYIgY2IW8jjfS\nqLz9LXB1TvslKmkRzkOLqytVHLd0GHw/RHHJivEsCWoz6SSY3sBG69kB/T8+vPj5\nebnRKpflW3CSGqqfPWAaq5H1b2fJjed2BnhKUV6hTkUxA0XRQHnaEQqQEhwyBz1K\nslANAoGBAIa8B0ACDJmWdPXj4gK1VKV5AgooJ9MQWP/15UpXxPEFPZIXy688sTYj\nU0cAOY5FeSNAEAmAm9y3OaLRYftmJiqXJFtxee7yziyq+yRl0lKhJd6ex7KCa+2Q\nFBN+h9tAswH5YSSYUQudMITxfaxpQmDafbMvK31zZNvkhTe87esQ\n-----END RSA PRIVATE KEY-----')
