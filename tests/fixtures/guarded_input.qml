import QtQuick
import "../.." as Calc
Item {
 width: 400; height: 80
 property int pasteRequests: 0
 property int lastSerial: -1
 property bool lastPrimary: false
 Calc.GuardedInput {
  id: field
  objectName: "field"
  width: 400; height: 60
  onEdited: function(updated) { value = updated }
  onPasteRequested: function(primary, capacity, serial) {
   parent.pasteRequests += 1; parent.lastSerial = serial; parent.lastPrimary = primary
  }
 }
}
