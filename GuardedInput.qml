import QtQuick

// TextEdit's plain-text canPaste path examines formats, not clipboard contents.
// All user paste gestures are intercepted before Qt's native paste handler.
FocusScope {
  id: control
  property string value: ""
  property int maximumLength: 4096
  readonly property int inputLimit: Math.max(0, Math.min(4096, maximumLength))
  readonly property string displayText: editor.text
  property alias font: editor.font
  property alias color: editor.color
  property alias selectionColor: editor.selectionColor
  property alias selectedTextColor: editor.selectedTextColor
  property alias cursorPosition: editor.cursorPosition
  property alias selectedText: editor.selectedText
  property alias cursorVisible: editor.cursorVisible
  property int pasteSerial: 0
  property var pasteSnapshot: null
  clip: true
  property real scrollOffset: 0
  property int inputRevision: 0
  property bool reverting: false
  property bool transaction: false
  property var lastState: null
  property var undoStates: []
  property var redoStates: []
  property bool mergeTyping: false
  property int typingEnd: -1
  readonly property bool canUndo: undoStates.length > 0
  readonly property bool canRedo: redoStates.length > 0
  signal edited(string value)
  signal shortcutPressed(var event)
  signal pasteRequested(bool primary, int capacity, int serial)
  signal rejected(string message)

  function ensureCursorVisible() {
    let left = editor.cursorRectangle.x
    let right = left + Math.max(1, editor.cursorRectangle.width)
    if (left < scrollOffset) scrollOffset = Math.max(0, left)
    else if (right > scrollOffset + width) scrollOffset = Math.max(0, right - width)
    scrollOffset = Math.min(scrollOffset, Math.max(0, editor.contentWidth - width + 1))
  }
  onWidthChanged: ensureCursorVisible()
  function syncValue() {
    if (!editor) return
    let bounded = value.slice(0, inputLimit).replace(/[\r\n\u2028\u2029\x00]/g, " ")
    let end = bounded.length ? bounded.charCodeAt(bounded.length - 1) : 0
    if (end >= 0xD800 && end <= 0xDBFF) bounded = bounded.slice(0, -1)
    if (editor.text === bounded) return
    reverting = true
    editor.text = bounded
    reverting = false
    undoStates = []
    redoStates = []
    mergeTyping = false
    lastState = captureState()
  }
  onValueChanged: syncValue()
  onInputLimitChanged: { undoStates = []; redoStates = []; syncValue() }
  Component.onCompleted: syncValue()
  function cancelPaste() { pasteSerial += 1; pasteSnapshot = null }
  onVisibleChanged: cancelPaste()
  onEnabledChanged: cancelPaste()
  function selectAll() { editor.selectAll() }
  function select(start, end) { editor.select(start, end) }
  function captureState() {
    return { text: editor.text, cursor: editor.cursorPosition,
      start: editor.selectionStart, end: editor.selectionEnd }
  }
  function syncCaret() {
    // Qt moves its cursor before announcing the matching text change.
    Qt.callLater(function() {
      if (!transaction && !reverting && lastState && lastState.text === editor.text) {
        let current = captureState()
        if (current.cursor !== lastState.cursor || current.start !== lastState.start
            || current.end !== lastState.end) mergeTyping = false
        lastState = current
      }
    })
  }
  function recordEdit(before, typing) {
    if (!before || before.text === editor.text) return
    if (!(typing && mergeTyping && before.cursor === typingEnd))
      undoStates = undoStates.concat([before]).slice(-32)
    redoStates = []
    mergeTyping = typing
    typingEnd = editor.cursorPosition
    lastState = captureState()
  }
  function restoreState(saved) {
    reverting = true
    editor.text = saved.text
    if (saved.start !== saved.end && saved.cursor === saved.start)
      editor.select(saved.end, saved.start)
    else editor.select(saved.start, saved.end)
    if (saved.start === saved.end) editor.cursorPosition = saved.cursor
    reverting = false
    lastState = captureState()
    mergeTyping = false
    control.edited(editor.text)
  }
  function undo() {
    if (!undoStates.length) return
    let saved = undoStates[undoStates.length - 1]
    redoStates = redoStates.concat([captureState()]).slice(-32)
    undoStates = undoStates.slice(0, -1)
    restoreState(saved)
  }
  function redo() {
    if (!redoStates.length) return
    let saved = redoStates[redoStates.length - 1]
    undoStates = undoStates.concat([captureState()]).slice(-32)
    redoStates = redoStates.slice(0, -1)
    restoreState(saved)
  }

  function requestPaste(primary) {
    if (!editor.activeFocus || !control.enabled || !control.visible) return
    pasteSerial += 1
    pasteSnapshot = { text: editor.text, cursor: editor.cursorPosition,
      start: editor.selectionStart, end: editor.selectionEnd, revision: inputRevision }
    pasteRequested(primary, Math.max(0, inputLimit - editor.text.length
      + editor.selectionEnd - editor.selectionStart), pasteSerial)
  }

  function applyPaste(value, serial) {
    let snapshot = pasteSnapshot
    if (serial !== pasteSerial || !snapshot || !editor.activeFocus
        || !control.enabled || !control.visible || editor.text !== snapshot.text
        || editor.cursorPosition !== snapshot.cursor
        || editor.selectionStart !== snapshot.start || editor.selectionEnd !== snapshot.end
        || inputRevision !== snapshot.revision)
      return false
    let incoming = String(value)
    if (/[\r\n\u2028\u2029\x00]/.test(incoming)
        || incoming.length > inputLimit - editor.text.length + snapshot.end - snapshot.start)
      return false
    pasteSnapshot = null
    transaction = true
    if (snapshot.end > snapshot.start) editor.remove(snapshot.start, snapshot.end)
    editor.insert(snapshot.start, incoming)
    editor.cursorPosition = snapshot.start + incoming.length
    transaction = false
    recordEdit(snapshot, false)
    control.edited(editor.text)
    return true
  }

  TextEdit {
    id: editor
    objectName: "guardedEditor"
    x: -control.scrollOffset
    width: Math.max(control.width, contentWidth)
    height: control.height
    focus: true
    text: ""
    textFormat: TextEdit.PlainText
    wrapMode: TextEdit.NoWrap
    verticalAlignment: TextEdit.AlignVCenter
    selectByMouse: true
    clip: true
    onActiveFocusChanged: {
      control.pasteSerial += 1; control.pasteSnapshot = null; control.mergeTyping = false
    }
    onInputMethodComposingChanged: {
      control.mergeTyping = false
      if (inputMethodComposing) control.lastState = control.captureState()
    }
    onCursorRectangleChanged: control.ensureCursorVisible()
    onContentWidthChanged: control.ensureCursorVisible()
    onCursorPositionChanged: { control.inputRevision += 1; control.syncCaret() }
    onSelectionStartChanged: { control.inputRevision += 1; control.syncCaret() }
    onSelectionEndChanged: { control.inputRevision += 1; control.syncCaret() }
    onTextChanged: {
      control.inputRevision += 1
      if (control.reverting || control.transaction) return
      if (text.length > control.inputLimit || /[\r\n\u2028\u2029\x00]/.test(text)) {
        control.reverting = true
        if (canUndo) undo()
        else text = control.value.slice(0, control.inputLimit).replace(/[\r\n\u2028\u2029\x00]/g, " ")
        control.reverting = false
        control.rejected("Input must be one line and at most " + control.maximumLength + " UTF-16 units")
        return
      }
      if (text !== control.value) {
        let before = control.lastState
        let inserted = before ? text.length - before.text.length : 0
        let typing = before && before.start === before.end && inserted === 1
          && text.slice(0, before.cursor) === before.text.slice(0, before.cursor)
          && text.slice(before.cursor + 1) === before.text.slice(before.cursor)
          && !inputMethodComposing
        control.recordEdit(before, typing)
        control.edited(text)
      } else {
        control.undoStates = []
        control.redoStates = []
        control.mergeTyping = false
        control.lastState = control.captureState()
      }
    }
    Keys.priority: Keys.BeforeItem
    Keys.onPressed: function(event) {
      event.accepted = false
      if (event.matches(StandardKey.Paste)) {
        control.requestPaste(false)
        event.accepted = true
      } else if (event.matches(StandardKey.Undo)) {
        control.undo(); event.accepted = true
      } else if (event.matches(StandardKey.Redo)) {
        control.redo(); event.accepted = true
      } else {
        control.lastState = control.captureState()
        if (event.key === Qt.Key_Left || event.key === Qt.Key_Right
            || event.key === Qt.Key_Home || event.key === Qt.Key_End)
          control.mergeTyping = false
        control.shortcutPressed(event)
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) event.accepted = true
      }
    }
  }

  MouseArea {
    anchors.fill: parent
    acceptedButtons: Qt.MiddleButton
    onPressed: function(mouse) {
      control.mergeTyping = false
      editor.forceActiveFocus()
      editor.cursorPosition = editor.positionAt(mouse.x + control.scrollOffset, mouse.y)
      editor.deselect()
      control.requestPaste(true)
    }
  }
}
