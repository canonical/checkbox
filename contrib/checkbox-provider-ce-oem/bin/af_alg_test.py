#!/usr/bin/python3
import socket
import argparse
import unittest
import struct


# This socket unit test is from python package /Lib/test/test_socket.py
class LinuxKernelCryptoAPI(unittest.TestCase):
    # tests for AF_ALG
    def create_alg(self, typ, name):
        sock = socket.socket(socket.AF_ALG, socket.SOCK_SEQPACKET, 0)
        try:
            sock.bind((typ, name))
        except FileNotFoundError as e:
            # type / algorithm is not available
            sock.close()
            print("Error: {}".format(e))
            raise Exception(
                "Error: Not able to use algorithm\n"
                "Please check kernel config!"
            )
        else:
            return sock

    def test_sha256(self):
        expected = bytes.fromhex(
            "ba7816bf8f01cfea414140de5dae2223b00361a396"
            "177a9cb410ff61f20015ad"
        )
        with self.create_alg("hash", "sha256") as algo:
            op, _ = algo.accept()
            with op:
                op.sendall(b"abc")
                self.assertEqual(op.recv(512), expected)

            op, _ = algo.accept()
            with op:
                op.send(b"a", socket.MSG_MORE)
                op.send(b"b", socket.MSG_MORE)
                op.send(b"c", socket.MSG_MORE)
                op.send(b"")
                self.assertEqual(op.recv(512), expected)
                print("hash: {}".format(op.recv(512).hex()))

    def test_aes_cbc(self):
        key = bytes.fromhex("06a9214036b8a15b512e03d534120006")
        iv = bytes.fromhex("3dafba429d9eb430b422da802c9fac41")
        msg = b"Single block msg"
        ciphertext = bytes.fromhex("e353779c1079aeb82708942dbe77181a")
        msglen = len(msg)
        with self.create_alg("skcipher", "cbc(aes)") as algo:
            algo.setsockopt(socket.SOL_ALG, socket.ALG_SET_KEY, key)
            op, _ = algo.accept()
            with op:
                op.sendmsg_afalg(
                    op=socket.ALG_OP_ENCRYPT, iv=iv, flags=socket.MSG_MORE
                )
                op.sendall(msg)
                self.assertEqual(op.recv(msglen), ciphertext)

            op, _ = algo.accept()
            with op:
                op.sendmsg_afalg([ciphertext], op=socket.ALG_OP_DECRYPT, iv=iv)
                self.assertEqual(op.recv(msglen), msg)

            # long message
            multiplier = 8
            longmsg = [msg] * multiplier
            op, _ = algo.accept()
            with op:
                op.sendmsg_afalg(longmsg, op=socket.ALG_OP_ENCRYPT, iv=iv)
                enc = op.recv(msglen * multiplier)
            self.assertEqual(len(enc), msglen * multiplier)
            self.assertEqual(enc[:msglen], ciphertext)

            op, _ = algo.accept()
            with op:
                op.sendmsg_afalg([enc], op=socket.ALG_OP_DECRYPT, iv=iv)
                dec = op.recv(msglen * multiplier)
            self.assertEqual(len(dec), msglen * multiplier)
            self.assertEqual(dec, msg * multiplier)
            print("skcipher: {}".format(dec.hex()))

    def test_aead_aes_gcm(self):
        key = bytes.fromhex("c939cc13397c1d37de6ae0e1cb7c423c")
        iv = bytes.fromhex("b3d8cc017cbb89b39e0f67e2")
        plain = bytes.fromhex("c3b3c41f113a31b73d9a5cd432103069")
        assoc = bytes.fromhex("24825602bd12a984e0092d3e448eda5f")
        expected_ct = bytes.fromhex("93fe7d9e9bfd10348a5606e5cafa7354")
        expected_tag = bytes.fromhex("0032a1dc85f1c9786925a2e71d8272dd")

        taglen = len(expected_tag)
        assoclen = len(assoc)
        with self.create_alg("aead", "gcm(aes)") as algo:
            algo.setsockopt(socket.SOL_ALG, socket.ALG_SET_KEY, key)
            algo.setsockopt(
                socket.SOL_ALG, socket.ALG_SET_AEAD_AUTHSIZE, None, taglen
            )

            # send assoc, plain and tag buffer in separate steps
            op, _ = algo.accept()
            with op:
                op.sendmsg_afalg(
                    op=socket.ALG_OP_ENCRYPT,
                    iv=iv,
                    assoclen=assoclen,
                    flags=socket.MSG_MORE,
                )
                op.sendall(assoc, socket.MSG_MORE)
                op.sendall(plain)
                res = op.recv(assoclen + len(plain) + taglen)
                self.assertEqual(expected_ct, res[assoclen:-taglen])
                self.assertEqual(expected_tag, res[-taglen:])

            # now with msg
            op, _ = algo.accept()
            with op:
                msg = assoc + plain
                op.sendmsg_afalg(
                    [msg],
                    op=socket.ALG_OP_ENCRYPT,
                    iv=iv,
                    assoclen=assoclen,
                )
                res = op.recv(assoclen + len(plain) + taglen)
                self.assertEqual(expected_ct, res[assoclen:-taglen])
                self.assertEqual(expected_tag, res[-taglen:])

            # create anc data manually
            pack_uint32 = struct.Struct("I").pack
            op, _ = algo.accept()
            with op:
                msg = assoc + plain
                op.sendmsg(
                    [msg],
                    (
                        [
                            socket.SOL_ALG,
                            socket.ALG_SET_OP,
                            pack_uint32(socket.ALG_OP_ENCRYPT),
                        ],
                        [
                            socket.SOL_ALG,
                            socket.ALG_SET_IV,
                            pack_uint32(len(iv)) + iv,
                        ],
                        [
                            socket.SOL_ALG,
                            socket.ALG_SET_AEAD_ASSOCLEN,
                            pack_uint32(assoclen),
                        ],
                    ),
                )
                res = op.recv(len(msg) + taglen)
                self.assertEqual(expected_ct, res[assoclen:-taglen])
                self.assertEqual(expected_tag, res[-taglen:])

            # decrypt and verify
            op, _ = algo.accept()
            with op:
                msg = assoc + expected_ct + expected_tag
                op.sendmsg_afalg(
                    [msg],
                    op=socket.ALG_OP_DECRYPT,
                    iv=iv,
                    assoclen=assoclen,
                )
                res = op.recv(len(msg) - taglen)
                self.assertEqual(plain, res[assoclen:])
                print("aead: {}".format(res[assoclen:].hex()))

    def test_rng(self):
        with self.create_alg("rng", "stdrng") as algo:
            # extra_seed = os.urandom(32)
            # algo.setsockopt(socket.SOL_ALG, socket.ALG_SET_KEY, extra_seed)
            op, _ = algo.accept()
            with op:
                rn = op.recv(32)
                self.assertEqual(len(rn), 32)
                print("rng: {}".format(rn.hex()))


def get_interrupt():
    interrupt_sum = 0
    with open("/proc/interrupts", "r") as a:
        data = a.readlines()
    for line in data:
        if ".jr" in line:
            interrupt_sum += int(line.split()[1])
    if not interrupt_sum:
        raise Exception("Error: Cannot find CAAM job ring interrupts")
    return interrupt_sum


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "type",
        choices=["aead", "hash", "skcipher", "rng"],
        help='AF_ALG type in "aead", "hash", "skcipher" and "rng"',
    )
    args = parser.parse_args()
    rng_test = LinuxKernelCryptoAPI()
    init_interrupt = get_interrupt()
    print(
        "CAAM Job ring interrupt before using Hardware RNG: {}".format(
            init_interrupt
        )
    )
    if args.type == "hash":
        print("Starting AF_ALG type {}...".format(args.type))
        rng_test.test_sha256()
    elif args.type == "skcipher":
        print("Starting AF_ALG type {}...".format(args.type))
        rng_test.test_aes_cbc()
    elif args.type == "aead":
        print("Starting AF_ALG type {}...".format(args.type))
        rng_test.test_aead_aes_gcm()
    elif args.type == "rng":
        print("Starting AF_ALG type {}...".format(args.type))
        rng_test.test_rng()
    else:
        raise Exception("Error: non-defined AF_ALG type!")
    current_interrupt = get_interrupt()
    print(
        "CAAM Job ring interrupt after using Hardware RNG: {}".format(
            current_interrupt
        )
    )
    if current_interrupt > init_interrupt:
        print("PASS: CAAM job ring interrupts have increased.")
    else:
        raise Exception("FAIL: CAAM job ring interrupts didn't increase!")


if __name__ == "__main__":
    main()
