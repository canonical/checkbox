#!/bin/bash

echo "nv_card_count: $(lspci | grep NVIDIA | grep VGA -c)"
exit 0
