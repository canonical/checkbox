/*
 * This file is part of Checkbox
 *
 * Copyright 2014 Canonical Ltd.
 *
 * Authors:
 * - Maciej Kisielewski <maciej.kisielewski@canonical.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
/*! \brief QML standalone shell

    This component serves as QML shell that embeds native QML plainbox jobs.
    The job it loads is specified by --job argument passed to qmlscene
    launching this component.
    Job to be run must have testingShell property that be used as a hook to
    'outside world'. The job should also define testDone signal that gets
    signalled once test is finished. The signal should pass result object
    containing following fields:
    'outcome' (mandatory): outcome of a test, e.g. 'pass', 'fail', 'undecided'.
    'suggestedOutcome': if outcome is 'undecided', than this suggestion will be
    presented to the user, letting them decide the final outcome of a test.
*/
import QtQuick 2.0
import Ubuntu.Components 0.1
import io.thp.pyotherside 1.2

MainView {
    id: mainView
    width: units.gu(100)
    height: units.gu(75)

    Python {
        id: py
        Component.onCompleted: {
            addImportPath(Qt.resolvedUrl('.'));
            py.importModule('pipe_handler', function() {
                console.log('pipe_handler.py imported');
                py.readAndClose(args.values['fd-in'], function(job_repr) {
                    testingShell.getTest = function() {
                        return JSON.parse(job_repr);
                    }
                    loader.setSource(args.values.job,
                                     {'testingShell': testingShell});
                });
            });
        }

        onError: console.error("python error: " + traceback)
        onReceived: console.log("pyotherside.send: " + data)

        function writeAndClose(str, fd, continuation) {
            py.call('pipe_handler.write_and_close', [str, fd], continuation);
        }
        function readAndClose(fd, continuation) {
            py.call('pipe_handler.read_and_close', [fd], continuation);
        }
    }

    // information and functionality passed to qml job component
    property var testingShell: {
        "name": "Plainbox qml shell",
        "pageStack": pageStack
    }

    Arguments {
        id: args
        Argument {
            name: "job"
            help: "QML-native job to run"
            required: true
            valueNames: ["PATH"]
        }
        Argument {
            name: "fd-out"
            help: "Descriptor number of pipe to write to"
            required: false
            valueNames: ["N"]
        }
        Argument {
            name: "fd-in"
            help: "Descriptor number of pipe to read from"
            required: false
            valueNames: ["N"]
        }
    }

    Loader {
        id: loader
        visible: false
        onLoaded: loader.item.testDone.connect(testDone)
    }

    function testDone(res) {
        py.writeAndClose(JSON.stringify(res), args.values['fd-out'], Qt.quit);
    }
    PageStack {
        id: pageStack
    }

}
