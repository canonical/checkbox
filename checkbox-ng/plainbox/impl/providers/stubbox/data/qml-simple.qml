import QtQuick 2.0
import Ubuntu.Components 0.1
import QtQuick.Layouts 1.1

Item {
    id: root
    signal testDone(var test);
    property var testingShell;

    Component.onCompleted: testingShell.pageStack.push(testPage)

    Page {
        id: testPage
        ColumnLayout {
            spacing: units.gu(10)
            anchors {
                margins: units.gu(5)
                fill: parent
            }

            Button {
                Layout.fillWidth: true; Layout.fillHeight: true
                text: i18n.tr("Pass")
                color: "#38B44A"
                onClicked: {
                    testDone({'outcome': 'pass'});
                }
            }

            Button {
                Layout.fillWidth: true; Layout.fillHeight: true
                text: i18n.tr("Fail")
                color: "#DF382C"
                onClicked: {
                    testDone({"outcome": "fail"});
                }
            }
        }
    }
}
