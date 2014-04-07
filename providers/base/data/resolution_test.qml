/*
 * This file is part of Checkbox.
 *
 * Copyright 2013 Canonical Ltd.
 * Written by:
 *   Sylvain Pineau <sylvain.pineau@canonical.com>
 *
 * Checkbox is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3,
 * as published by the Free Software Foundation.
 *
 * Checkbox is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Checkbox.  If not, see <http://www.gnu.org/licenses/>.
 */

import QtQuick 2.0
import QtQuick.Window 2.0

Rectangle {
    border.color: "lime"
    border.width: 15
    color: "transparent"
    Text {
        anchors.centerIn: parent
        text: Screen.width + " x " + Screen.height
        font.bold: true
        font.pointSize: 80
        color: "lime"
        smooth: true
    }
}

