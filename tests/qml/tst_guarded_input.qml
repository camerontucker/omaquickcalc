import QtQuick
import QtTest
import "../.." as Calc
TestCase {
 name: "GuardedInput"
 visible: true
 width: 400; height: 80
 when: windowShown
 Calc.GuardedInput {
  id: input
  width: 400; height: 60
  onEdited: function(updated) { value = updated }
  onPasteRequested: function(primary, capacity, serial) {
   test.lastSerial = serial; test.lastPrimary = primary; test.capacity = capacity; test.requests += 1
  }
 }
 id: test
 property int lastSerial: -1
 property bool lastPrimary: false
 property int capacity: -1
 property int requests: 0
 function init() { input.value = ""; input.maximumLength = 4096; input.forceActiveFocus(); requests = 0 }
 function test_typing_selection_undo() {
  keyClick(Qt.Key_A); keyClick(Qt.Key_B); keyClick(Qt.Key_C)
  compare(input.value, "abc")
  input.select(1, 2); compare(input.selectedText, "b")
  keyClick(Qt.Key_X); compare(input.value, "axc")
  input.undo(); compare(input.value, "abc")
  input.redo(); compare(input.value, "axc")
 }
 function test_explicit_paste_shortcuts_do_not_use_native_paste() {
  keyClick(Qt.Key_V, Qt.ControlModifier); compare(requests, 1); compare(input.value, "")
  keyClick(Qt.Key_Insert, Qt.ShiftModifier); compare(requests, 2)
  verify(input.applyPaste("12+3", lastSerial)); compare(input.value, "12+3")
 }
 function test_selection_paste_is_one_undo_redo_transaction() {
  input.value = "12345"; input.select(1,4)
  keyClick(Qt.Key_V, Qt.ControlModifier)
  verify(input.applyPaste("abc", lastSerial)); compare(input.value, "1abc5")
  input.undo(); compare(input.value, "12345")
  input.redo(); compare(input.value, "1abc5")
 }
 function test_paste_typing_undo_redo_and_branching() {
  input.value = "12345"; input.select(1,4)
  keyClick(Qt.Key_V, Qt.ControlModifier); verify(input.applyPaste("abc", lastSerial))
  keyClick(Qt.Key_X); compare(input.value, "1abcx5")
  keyClick(Qt.Key_Z, Qt.ControlModifier); compare(input.value, "1abc5")
  keyClick(Qt.Key_Z, Qt.ControlModifier); compare(input.value, "12345")
  input.redo(); compare(input.value, "1abc5")
  keyClick(Qt.Key_Y); compare(input.value, "1abcy5")
  verify(!input.canRedo)
 }
 function test_typing_groups_and_undo_memory_is_bounded() {
  keyClick(Qt.Key_A); keyClick(Qt.Key_B); keyClick(Qt.Key_C)
  input.undo(); compare(input.value, "")
  input.redo(); compare(input.value, "abc")
  for (var i = 0; i < 40; i++) {
   keyClick(Qt.Key_V, Qt.ControlModifier); verify(input.applyPaste("x", lastSerial))
  }
  verify(input.undoStates.length <= 32)
 }
 function test_rejects_stale_response_after_typing_or_selection() {
  input.value = "12"; input.cursorPosition = 2
  keyClick(Qt.Key_V, Qt.ControlModifier); keyClick(Qt.Key_3)
  verify(!input.applyPaste("4", lastSerial)); compare(input.value, "123")
  keyClick(Qt.Key_V, Qt.ControlModifier); input.select(0,1)
  verify(!input.applyPaste("4", lastSerial)); compare(input.value, "123")
 }
 function test_limits_plain_text_and_single_line() {
  input.maximumLength = 3; input.value = "12"; input.cursorPosition = 2
  keyClick(Qt.Key_V, Qt.ControlModifier); compare(capacity, 1)
  verify(!input.applyPaste("34", lastSerial))
  verify(!input.applyPaste("\n", lastSerial))
  verify(input.applyPaste("3", lastSerial)); compare(input.value, "123")
  keyClick(Qt.Key_4); compare(input.value, "123")
  keyClick(Qt.Key_Return); compare(input.value, "123")
 }
 function test_changed_then_restored_input_still_rejects_old_response() {
  input.value = "12"; input.cursorPosition = 2
  keyClick(Qt.Key_V, Qt.ControlModifier)
  keyClick(Qt.Key_3); keyClick(Qt.Key_Backspace)
  compare(input.value, "12")
  verify(!input.applyPaste("4", lastSerial))
 }
 function test_visibility_change_invalidates_pending_paste() {
  keyClick(Qt.Key_V, Qt.ControlModifier)
  input.visible = false; input.visible = true; input.forceActiveFocus()
  verify(!input.applyPaste("4", lastSerial))
 }
 function test_actual_focus_change_invalidates_pending_paste() {
  keyClick(Qt.Key_V, Qt.ControlModifier)
  test.forceActiveFocus(); input.forceActiveFocus()
  verify(!input.applyPaste("4", lastSerial))
 }
 function test_external_values_are_bounded_before_rendering() {
  input.maximumLength = 3; input.value = "123456789"
  compare(input.displayText, "123")
  input.value = "12\n"; compare(input.displayText, "12 ")
  input.value = "12😀"; compare(input.displayText, "12")
 }
 function test_paste_remains_literal_plain_text() {
  keyClick(Qt.Key_V, Qt.ControlModifier)
  verify(input.applyPaste("<b>x</b>", lastSerial))
  compare(input.value, "<b>x</b>")
 }
 function test_long_line_scrolls_to_keep_caret_visible() {
  input.value = new Array(121).join("x"); input.cursorPosition = 120
  verify(input.scrollOffset > 0)
  input.cursorPosition = 0; compare(input.scrollOffset, 0)
 }
 function test_middle_click_requests_primary_selection() {
  mouseClick(input, 10, 10, Qt.MiddleButton)
  compare(requests, 1); compare(lastPrimary, true); compare(input.value, "")
 }
}
