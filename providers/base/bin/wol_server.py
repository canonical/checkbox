#!/usr/bin/python3

# Copyright 2025 Canonical Ltd.
# Written by:
#   Eugene Wu <eugene.wu@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import logging
import threading
import time
import subprocess
import shlex
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi import HTTPException

app = FastAPI()

LOG_LEVEL = "DEBUG"
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


@app.post("/")
async def testing(wol_request: dict):
    try:
        ret_server = tasker_main(wol_request)
        return JSONResponse(
            content=jsonable_encoder(ret_server), status_code=200
        )
    except Exception as e:
        logger.error("exception in testing: {}".format(e))
        raise HTTPException(status_code=500, detail=str(e))


def send_wol_command(Wol_Info: dict):
    dut_mac = Wol_Info["DUT_MAC"]
    dut_ip = Wol_Info["DUT_IP"]
    wake_type = Wol_Info["wake_type"]

    command_dict = {
        "g": "wakeonlan {}".format(dut_mac),
        "a": "ping {}".format(dut_ip),
    }

    try:
        logger.debug("Wake on lan command: {}".format(command_dict[wake_type]))
        output = subprocess.check_output(shlex.split(command_dict[wake_type]))
        logger.debug({output})
        return True

    except Exception as e:
        logger.error("Error occurred in tasker_main: {}".format(e))
        return False


def tasker_main(request: dict) -> dict:
    try:
        # Extracting necessary fields from the request
        dut_ip = request.get("DUT_IP")
        delay = request.get("delay")

        if not dut_ip or delay is None:
            logger.error("Missing required fields: DUT_IP or delay")
            return {"result": "error", "message": "Missing required fields"}

        logger.info("Received request: {}".format(request))
        logger.info("DUT_IP: {}".format(dut_ip))

        # Starting the task in a separate thread
        thread = threading.Thread(target=run_task, args=(request, delay))
        thread.start()

        # Returning success response
        return {"result": "success"}

    except Exception as e:
        logger.error(
            "Error occurred while processing the request: {}".format(e)
        )
        return {"result": "error", "message": str(e)}


def is_pingable(ip_address):
    try:
        command = ["ping", "-c", "1", "-W", "1", ip_address]
        output = subprocess.check_output(
            command, stderr=subprocess.STDOUT, universal_newlines=True
        )
        logger.debug("ping: {}".format(output))
        return True
    except subprocess.CalledProcessError as e:
        logger.error("An error occurred while ping the DUT: {}".format(e))
        return False


def run_task(data, delay):
    dut_ip = data["DUT_IP"]
    delay = data["delay"]
    retry_times = data["retry_times"]

    for attempt in range(retry_times):
        logger.debug("retry times: {}".format(attempt))
        time.sleep(delay)

        try:
            # send wol command to the dut_mac
            logger.debug("send wol command to the dut_mac")
            send_wol_command(data)

            # delay a little time, ping the DUT,
            # if not up, send wol command again
            logger.debug("ping DUT to see if it had been waked up")
            time.sleep(delay)
            if is_pingable(dut_ip):
                logger.info("{} is pingable, the DUT is back".format(dut_ip))
                return True
            else:
                logger.info(
                    "{} is NOT pingable, the DUT is not back.".format(dut_ip)
                )

        except Exception as e:
            logger.error("Error occurred in tasker_main: {}".format(e))

    return False
