import QtQuick
import QtTest
import "../.." as OmaQuickCalc

TestCase {
  name: "OmaQuickCalcPlainText"

  Component {
    id: labelComponent
    OmaQuickCalc.PlainText {}
  }

  Component {
    id: detailComponent
    TextEdit {
      readOnly: true
      textFormat: TextEdit.PlainText
    }
  }

  function test_markup_shaped_values_remain_plain_text() {
    var label = createTemporaryObject(labelComponent, this, {
      text: '<img src="file:///tmp/should-not-load"> <b>value</b>'
    })
    verify(label !== null)
    compare(label.textFormat, Text.PlainText)
    compare(label.text, '<img src="file:///tmp/should-not-load"> <b>value</b>')
  }

  function test_detail_markup_shaped_values_remain_plain_text() {
    var detail = createTemporaryObject(detailComponent, this, {
      text: '<img src="file:///tmp/should-not-load"> <b>result</b>'
    })
    verify(detail !== null)
    compare(detail.textFormat, TextEdit.PlainText)
    compare(detail.text, '<img src="file:///tmp/should-not-load"> <b>result</b>')
  }
}
