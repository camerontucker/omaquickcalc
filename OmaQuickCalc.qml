pragma ComponentBehavior: Bound

import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import qs.Commons
import qs.Ui
import "OmaQuickCalcModel.js" as CalcModel

Item {
  id: root

  // Injected by omarchy-shell when the plugin is loaded.
  property var shell: null
  property var manifest: null

  property bool opened: false
  property string expression: ""
  property string result: ""
  property string rawResult: ""
  property string resultKind: "math"
  property string normalizedExpression: ""
  property string swapExpression: ""
  property bool resultDynamic: false
  property string resultColor: ""
  property var resultFormats: []
  property string rateDate: ""
  property string rateSource: ""
  property int rateAgeDays: -1
  property bool rateStale: false
  property string rateStatusOverride: ""
  property string errorText: ""
  property string statusText: ""
  property string pendingAction: ""
  property string activeAction: ""

  property var settings: CalcModel.parseSettings("{}")
  property var history: []
  property bool historyOpen: false
  property string historyQuery: ""
  property int selectedHistoryIndex: -1
  property bool detailOpen: false
  property bool actionMenuOpen: false
  property int selectedActionIndex: 0
  property var actionItems: []
  property bool clearConfirmOpen: false

  // Launch setup is deliberately separate from calculator preferences. A
  // shortcut is written only after the user selects it and confirms the
  // exact change in the first-run screen.
  property bool launchStateLoaded: false
  property bool launchSetupComplete: false
  property bool setupOpen: false
  property bool setupForced: false
  property string setupPage: "choices"
  property int setupSelectedIndex: 0
  property var setupShortcutOptions: [
    { shortcut: "SUPER + ALT + Q", conflict: false, checked: false, description: "" },
    { shortcut: "SUPER + SHIFT + Q", conflict: false, checked: false, description: "" },
    { shortcut: "SUPER + CTRL + ALT + Q", conflict: false, checked: false, description: "" }
  ]
  property string setupPendingShortcut: ""
  property string setupPendingDescription: ""
  property string setupError: ""
  property string setupStatusOutput: ""
  property string setupApplyOutput: ""
  property bool setupApplyStarted: false
  property bool launcherChecked: false
  property bool launcherReady: false

  property bool storageReady: false
  property bool defaultConfigWritten: false
  property bool settingsMigrationWritten: false
  property bool backendChecked: false
  property bool backendAvailable: false
  property bool backendCheckStarted: false
  property bool qalcChecked: false
  property bool qalcAvailable: false
  property bool pythonChecked: false
  property bool pythonAvailable: false
  property bool pythonCheckStarted: false
  property bool clipboardChecked: false
  property bool clipboardAvailable: false
  property bool clipboardCheckStarted: false
  property bool installRequested: false
  property bool exchangeRefreshStarted: false
  property bool exchangeRefreshForResult: false
  property bool copyCloseAfter: false
  property bool copyProcessStarted: false
  property bool transformActive: false
  property string transformToken: ""
  property string transformOperand: ""
  property string transformOriginWindow: ""
  property int transformOriginPid: 0
  property bool transformOriginTerminal: false
  property string transformReadOutput: ""
  property bool transformReadStarted: false
  property bool replaceProcessStarted: false

  // Evaluation state. Processes are allowed to finish while the user types;
  // generations ensure an old result can never replace a newer expression.
  property int evaluationGeneration: 0
  property int activeGeneration: -1
  property string pendingExpression: ""
  property int pendingTimeoutMs: 250
  property string activeExpression: ""
  property string activeOutput: ""
  property string activeErrorOutput: ""
  property int activeExitCode: -1
  property bool activeProcessExited: true
  property bool activeStdoutFinished: true
  property bool activeStderrFinished: true
  property bool rerunPending: false

  readonly property string home: Quickshell.env("HOME")
  readonly property string dataHome: Quickshell.env("XDG_DATA_HOME") || (home + "/.local/share")
  readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME") || (home + "/.config")
  readonly property string dataDir: dataHome + "/omaquickcalc"
  readonly property string configDir: configHome + "/omaquickcalc"
  readonly property string historyPath: dataDir + "/history.json"
  readonly property string configPath: configDir + "/config.json"
  readonly property string launchStatePath: configDir + "/launch.json"
  readonly property string launcherPath: dataHome + "/applications/"
    + pluginId + ".desktop"
  readonly property string pluginDir: (manifest && manifest.__sourceDir) || ""
  readonly property string backendPath: pluginDir + "/omaquickcalc_backend.py"
  readonly property string setupHelperPath: pluginDir + "/omaquickcalc_setup.py"
  readonly property string transformHelperPath: pluginDir + "/omaquickcalc_transform.py"

  property string fontFamily: Style.font.menuFamily
  property color background: Color.menu.background
  property color foreground: Color.menu.text
  property color border: Color.menu.border
  property color scrim: Color.menu.scrim
  property color accent: Color.accent
  property color urgent: Color.urgent
  readonly property color cardBackground: Util.alpha(background, settings.backgroundOpacity)
  property var borderSpec: Border.surfaceSpec("menu", "border", border, Math.max(1, Style.space(2)))
  readonly property int cornerRadius: Style.cornerRadius
  readonly property int contentMargin: Style.space(18)
  readonly property int rowContentHeight: Math.max(Style.space(36), Style.font.heading + Style.space(8))
  readonly property int resultRowHeight: result.length > 0 ? Style.space(68) : 0
  readonly property int baseCardHeight: rowContentHeight + resultRowHeight + contentMargin * 2
  readonly property var displayHistory: CalcModel.filterHistory(history, historyQuery)
  readonly property int visibleHistoryRows: Math.min(5, displayHistory.length)
  readonly property int historyExtraHeight: historyOpen
    ? Style.space(54) + Math.max(1, visibleHistoryRows) * Style.space(42) + Style.space(26)
    : 0
  readonly property int detailExtraHeight: detailOpen ? Style.space(194) : 0
  readonly property int actionExtraHeight: actionMenuOpen
    ? Style.space(14) + Math.min(7, Math.max(1, actionItems.length)) * Style.space(42) + Style.space(26)
    : 0
  readonly property int cardWidth: Math.min(Style.space(720), panel.width - Style.gapsOut * 2)
  readonly property int cardHeight: setupOpen ? Style.space(380) : baseCardHeight
    + Math.max(historyExtraHeight, detailExtraHeight, actionExtraHeight)
  readonly property string pluginId: (manifest && manifest.id)
    || "io.github.camerontucker.omaquickcalc"
  readonly property string pluginVersion: (manifest && manifest.version) || "0"
  readonly property var setupItems: {
    if (setupPage === "choices") return [
      {
        id: "replace",
        label: "Replace Omacalc shortcut",
        detail: "Super + Ctrl + Q · enables selection transforms",
        enabled: true
      },
      {
        id: "alternate",
        label: "Choose another shortcut",
        detail: "Pick a shortcut for launch and selection transforms",
        enabled: true
      },
      {
        id: "skip",
        label: "Skip shortcut setup",
        detail: launcherReady ? "Launch from Super + Space anytime"
          : "Continue without changing a shortcut",
        enabled: true
      }
    ]
    if (setupPage === "alternatives") {
      var alternatives = []
      for (var optionIndex = 0; optionIndex < setupShortcutOptions.length; optionIndex += 1) {
        var option = setupShortcutOptions[optionIndex]
        alternatives.push({
          id: "shortcut",
          shortcut: option.shortcut,
          label: root.prettyShortcut(option.shortcut),
          detail: !option.checked ? "Checking existing bindings…"
            : (option.inspectionFailed ? "Couldn’t inspect this shortcut"
              : (option.conflict ? "Currently: " + option.description : "Available")),
          description: option.description,
          checked: option.checked,
          enabled: true
        })
      }
      return alternatives
    }
    if (setupPage === "confirm") return [
      {
        id: "apply",
        label: "Use " + root.prettyShortcut(setupPendingShortcut),
        detail: setupPendingDescription
          ? "Replace “" + setupPendingDescription + "”"
          : "Add this OmaQuickCalc shortcut",
        enabled: true
      },
      { id: "back", label: "Go back", detail: "Make no changes", enabled: true }
    ]
    if (setupPage === "error") return [
      { id: "retry", label: "Try again", detail: setupError, enabled: true },
      { id: "back", label: "Go back", detail: "Make no changes", enabled: true }
    ]
    return []
  }
  readonly property string setupTitle: {
    if (setupPage === "alternatives") return "Choose a shortcut"
    if (setupPage === "confirm") return "Confirm shortcut change"
    if (setupPage === "applying") return "Applying shortcut…"
    if (setupPage === "error") return "Shortcut wasn’t changed"
    return "How should OmaQuickCalc launch?"
  }
  readonly property string setupDescription: {
    if (setupPage === "alternatives")
      return "Existing bindings are shown before you confirm any replacement."
    if (setupPage === "confirm")
      return "The shortcut may capture short numeric selections. Only OmaQuickCalc’s marked binding block is managed."
    if (setupPage === "applying")
      return "Validating the binding with Hyprland. A failed change is rolled back automatically."
    if (setupPage === "error") return "Your previous Hyprland configuration is still intact."
    if (!launcherChecked) return "Preparing the Super + Space launcher entry. A shortcut is optional."
    if (launcherReady)
      return "Super + Space stays clipboard-blind. A selection-aware keyboard shortcut is optional."
    return "An existing unowned launcher entry was left untouched. A shortcut is optional."
  }
  readonly property string displayResult: CalcModel.singleLine(result)
  readonly property string rateSummary: {
    if (resultKind !== "currency" || !rateDate) return ""
    if (rateStatusOverride) return rateStatusOverride
    if (rateStale) return "Rates " + rateDate + " · " + String(rateAgeDays) + "d old"
    return (rateSource || "Rates") + " · " + rateDate
  }
  readonly property bool statusIsError: errorText.length > 0
  readonly property string visibleStatus: {
    if (!backendChecked) return "Checking calculator…"
    if (!backendAvailable) {
      if (installRequested) return "Installing… authenticate in the terminal"
      if (settings.qalcBinary !== "qalc" && qalcChecked && !qalcAvailable)
        return "Calculator engine unavailable"
      if (pythonChecked && !pythonAvailable) return "Enter to install Python"
      return "Enter to install calculator support"
    }
    if (errorText) return CalcModel.singleLine(errorText)
    if (clipboardChecked && !clipboardAvailable) return "Enter to install clipboard support"
    return statusText
  }

  onExpressionChanged: {
    if (root.opened && !root.setupOpen) root.scheduleEvaluation()
  }

  function open(payloadJson) {
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (error) { payload = ({}) }

    if (payload.fontFamily) root.fontFamily = String(payload.fontFamily)
    root.opened = true
    root.setupForced = Boolean(payload.setup)
    root.historyOpen = false
    root.historyQuery = ""
    root.detailOpen = false
    root.actionMenuOpen = false
    root.clearConfirmOpen = false
    root.pendingAction = ""
    root.transformActive = false
    root.transformToken = String(payload.transformToken || "")
    root.transformOperand = ""
    root.transformOriginWindow = ""
    root.transformOriginPid = 0
    root.transformOriginTerminal = false
    root.expression = payload.expression ? String(payload.expression) : ""
    root.result = ""
    root.clearResultMetadata()
    root.errorText = ""
    root.statusText = root.transformToken ? "Reading selected text…" : ""

    if (root.transformToken) root.startTransformRead()

    if (!root.backendChecked || !root.backendAvailable) root.startBackendCheck()
    if (root.setupForced || !root.launchSetupComplete) root.beginLaunchSetup()
    else root.focusCalculator()
  }

  function close() {
    if (root.opened && root.settings.saveOnClose && root.result)
      root.addCurrentToHistory()
    root.opened = false
    root.historyOpen = false
    root.historyQuery = ""
    root.detailOpen = false
    root.actionMenuOpen = false
    root.clearConfirmOpen = false
    root.setupOpen = false
    root.setupForced = false
    root.pendingAction = ""
    root.transformActive = false
    root.transformToken = ""
    root.transformOperand = ""
    root.transformOriginWindow = ""
    root.transformOriginPid = 0
    root.transformOriginTerminal = false
    root.installRequested = false
    installerPoll.stop()
    evaluationTimer.stop()
    root.evaluationGeneration += 1
    root.pendingExpression = ""
    root.expression = ""
    root.result = ""
    root.clearResultMetadata()
    root.errorText = ""
    root.statusText = ""
  }

  function dismiss() {
    root.close()
    if (root.shell && typeof root.shell.hide === "function")
      root.shell.hide(root.pluginId)
  }

  function toggle() {
    if (root.opened) root.dismiss()
    else root.open("{}")
  }

  function prettyShortcut(shortcut) {
    return String(shortcut || "")
      .replace(/SUPER/g, "Super")
      .replace(/CTRL/g, "Ctrl")
      .replace(/ALT/g, "Alt")
      .replace(/SHIFT/g, "Shift")
  }

  function launcherContents() {
    return "[Desktop Entry]\n"
      + "Type=Application\n"
      + "Name=OmaQuickCalc\n"
      + "GenericName=Calculator\n"
      + "Comment=Summon a fast calculation palette\n"
      + "Exec=omarchy-shell shell summon " + root.pluginId + " {}\n"
      + "Icon=accessories-calculator\n"
      + "Terminal=false\n"
      + "Categories=Utility;Calculator;\n"
      + "Keywords=calculator;calc;math;currency;units;timezone;color;\n"
      + "StartupNotify=false\n"
      + "Actions=Setup;\n"
      + "X-OmaQuickCalc-Managed=true\n"
      + "X-OmaQuickCalc-Version=" + root.pluginVersion + "\n\n"
      + "[Desktop Action Setup]\n"
      + "Name=Configure launch shortcut\n"
      + "Exec=omarchy-shell shell summon " + root.pluginId + " {\"setup\":true}\n"
  }

  function ensureLauncher(raw) {
    var current = String(raw || "")
    root.launcherChecked = true
    if (current && current.indexOf("X-OmaQuickCalc-Managed=true") < 0) {
      root.launcherReady = false
      return
    }
    var expected = root.launcherContents()
    if (current !== expected) launcherFile.setText(expected)
    root.launcherReady = true
  }

  function focusCalculator() {
    root.setupOpen = false
    Qt.callLater(function() {
      expressionInput.forceActiveFocus()
      expressionInput.selectAll()
    })
  }

  function startTransformRead() {
    if (!root.transformToken || selectionRead.running) return
    root.transformReadOutput = ""
    root.transformReadStarted = true
    selectionRead.command = [
      "python3", root.transformHelperPath, "consume", "--token", root.transformToken
    ]
    selectionRead.running = true
  }

  function finishTransformRead(exitCode) {
    if (!root.transformReadStarted) return
    root.transformReadStarted = false
    root.transformToken = ""
    var payload = ({})
    try { payload = JSON.parse(root.transformReadOutput || "{}") } catch (error) { payload = ({}) }
    root.transformReadOutput = ""
    if (!root.opened) return
    if (exitCode !== 0 || !payload.selection || !payload.windowAddress || !payload.windowPid) {
      root.statusText = "No numeric selection found"
      return
    }
    root.transformActive = true
    root.transformOperand = String(payload.selection)
    root.transformOriginWindow = String(payload.windowAddress)
    root.transformOriginPid = Number(payload.windowPid)
    root.transformOriginTerminal = Boolean(payload.terminal)
    root.statusText = ""
    root.scheduleEvaluation()
    root.focusCalculator()
  }

  function calculationExpression() {
    var query = root.expression.trim()
    var operand = root.transformOperand.trim()
    if (!root.transformActive || !operand) return query
    if (!query) return operand
    if (/^[+-]?\d+(?:\.\d+)?%\s+off$/i.test(query)) return query + " " + operand
    if (/^[+-]?\d+(?:\.\d+)?%\s+tip$/i.test(query)) return query + " on " + operand
    if (/^in\s+/i.test(query)) return operand + " to " + query.replace(/^in\s+/i, "")
    return operand + " " + query
  }

  function beginLaunchSetup() {
    root.setupOpen = true
    root.setupPage = "choices"
    root.setupSelectedIndex = 0
    root.setupPendingShortcut = ""
    root.setupPendingDescription = ""
    root.setupError = ""
    if (!shortcutStatus.running) {
      root.setupStatusOutput = ""
      shortcutStatus.command = [
        "python3", root.setupHelperPath, "shortcut-status",
        "SUPER + CTRL + Q", "SUPER + ALT + Q", "SUPER + SHIFT + Q",
        "SUPER + CTRL + ALT + Q"
      ]
      shortcutStatus.running = true
    }
    Qt.callLater(function() { setupPane.forceActiveFocus() })
  }

  function loadLaunchState(raw) {
    var state = ({})
    try { state = JSON.parse(String(raw || "{}")) } catch (error) { state = ({}) }
    root.launchSetupComplete = state.version === 2 && Boolean(state.complete)
    root.launchStateLoaded = true
    if (!root.opened) return
    if (root.setupForced || !root.launchSetupComplete) {
      if (!root.setupOpen) root.beginLaunchSetup()
    } else root.focusCalculator()
  }

  function saveLaunchState(choice, shortcut) {
    var state = {
      version: 2,
      complete: true,
      choice: String(choice || "skip"),
      shortcut: String(shortcut || "")
    }
    launchStateFile.setText(JSON.stringify(state, null, 2) + "\n")
    root.launchSetupComplete = true
  }

  function finishLaunchSetup(choice, shortcut) {
    root.saveLaunchState(choice, shortcut)
    root.setupForced = false
    root.focusCalculator()
  }

  function finishShortcutStatus(exitCode) {
    var payload = ({})
    try { payload = JSON.parse(root.normalizeOutput(root.setupStatusOutput) || "{}") }
    catch (error) { payload = ({}) }
    if (exitCode !== 0 || !payload.ok || !Array.isArray(payload.shortcuts)) {
      var unchecked = []
      for (var failedIndex = 0; failedIndex < root.setupShortcutOptions.length; failedIndex += 1) {
        unchecked.push({
          shortcut: root.setupShortcutOptions[failedIndex].shortcut,
          conflict: true,
          checked: true,
          inspectionFailed: true,
          description: "Existing binding status unknown"
        })
      }
      root.setupShortcutOptions = unchecked
      return
    }
    var alternatives = []
    for (var index = 0; index < payload.shortcuts.length; index += 1) {
      var status = payload.shortcuts[index]
      if (status.shortcut === "SUPER + CTRL + Q") continue
      alternatives.push({
        shortcut: String(status.shortcut),
        conflict: Boolean(status.conflict),
        checked: true,
        inspectionFailed: false,
        description: String(status.description || "")
      })
    }
    if (alternatives.length > 0) root.setupShortcutOptions = alternatives
  }

  function chooseSetupItem(index) {
    if (index < 0 || index >= root.setupItems.length) return
    var item = root.setupItems[index]
    if (item.enabled === false || root.setupPage === "applying") return

    if (root.setupPage === "choices") {
      if (item.id === "replace") {
        root.setupPendingShortcut = "SUPER + CTRL + Q"
        root.setupPendingDescription = "Calculator (Omacalc)"
        root.setupPage = "confirm"
      } else if (item.id === "alternate") {
        root.setupPage = "alternatives"
      } else if (item.id === "skip") {
        root.finishLaunchSetup("skip", "")
        return
      }
      root.setupSelectedIndex = 0
      return
    }

    if (root.setupPage === "alternatives") {
      root.setupPendingShortcut = String(item.shortcut)
      root.setupPendingDescription = String(item.description || "")
      root.setupPage = "confirm"
      root.setupSelectedIndex = 0
      return
    }

    if (item.id === "back") {
      root.setupPage = "choices"
      root.setupSelectedIndex = 0
      return
    }
    if (item.id === "apply" || item.id === "retry") root.applySetupShortcut()
  }

  function applySetupShortcut() {
    if (!root.setupPendingShortcut || setupApply.running) return
    root.setupPage = "applying"
    root.setupSelectedIndex = 0
    root.setupError = ""
    root.setupApplyOutput = ""
    root.setupApplyStarted = true
    setupApply.command = [
      "python3", root.setupHelperPath, "apply-shortcut", root.setupPendingShortcut,
      "--plugin-id", root.pluginId
    ]
    setupApply.running = true
  }

  function finishSetupApply(exitCode) {
    if (!root.setupApplyStarted) return
    root.setupApplyStarted = false
    var payload = ({})
    try { payload = JSON.parse(root.normalizeOutput(root.setupApplyOutput) || "{}") }
    catch (error) { payload = ({}) }
    if (exitCode === 0 && payload.ok) {
      root.finishLaunchSetup("shortcut", root.setupPendingShortcut)
      return
    }
    root.setupError = String(payload.error || "Could not apply this shortcut")
    root.setupPage = "error"
    root.setupSelectedIndex = 0
    Qt.callLater(function() { setupPane.forceActiveFocus() })
  }

  function moveSetupSelection(delta) {
    if (root.setupItems.length === 0) return
    root.setupSelectedIndex = Math.max(0, Math.min(root.setupItems.length - 1,
      root.setupSelectedIndex + delta))
  }

  function setupBack() {
    if (root.setupPage === "alternatives" || root.setupPage === "confirm"
        || root.setupPage === "error") {
      root.setupPage = "choices"
      root.setupSelectedIndex = 0
    } else root.dismiss()
  }

  function handleSetupKey(event) {
    if (event.key === Qt.Key_Escape) {
      root.setupBack()
      return true
    }
    if (event.key === Qt.Key_Up) {
      root.moveSetupSelection(-1)
      return true
    }
    if (event.key === Qt.Key_Down) {
      root.moveSetupSelection(1)
      return true
    }
    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      root.chooseSetupItem(root.setupSelectedIndex)
      return true
    }
    return false
  }

  function normalizeOutput(raw) {
    return String(raw || "")
      .replace(/\x1b\[[0-9;]*m/g, "")
      .replace(/\r\n/g, "\n")
      .trim()
  }

  function clearResultMetadata() {
    root.rawResult = ""
    root.resultKind = "math"
    root.normalizedExpression = ""
    root.swapExpression = ""
    root.resultDynamic = false
    root.resultColor = ""
    root.resultFormats = []
    root.rateDate = ""
    root.rateSource = ""
    root.rateAgeDays = -1
    root.rateStale = false
    root.rateStatusOverride = ""
    root.actionItems = []
  }

  function loadSettings(raw) {
    var rawText = String(raw || "").trim()
    var oldBinary = root.settings.qalcBinary
    root.settings = CalcModel.parseSettings(raw)
    root.pendingTimeoutMs = root.settings.previewTimeoutMs

    if (!rawText && root.storageReady && !root.defaultConfigWritten) {
      root.defaultConfigWritten = true
      configFile.setText(JSON.stringify(root.settings, null, 2) + "\n")
    } else if (rawText && root.storageReady && !root.settingsMigrationWritten) {
      var parsed = ({})
      try { parsed = JSON.parse(rawText) } catch (error) { parsed = ({}) }
      if (parsed.backgroundOpacity === undefined
          || parsed.historyRetentionDays === undefined
          || parsed.remPx === undefined
          || parsed.workdayHours === undefined
          || parsed.precision === undefined
          || parsed.clockFormat === undefined
          || parsed.defaultFromCurrency === undefined
          || parsed.defaultToCurrency === undefined
          || parsed.rateStaleDays === undefined) {
        root.settingsMigrationWritten = true
        configFile.setText(JSON.stringify(root.settings, null, 2) + "\n")
      }
    }

    if (root.settings.historyMode === "persistent") historyFile.reload()
    else root.history = []

    if (oldBinary !== root.settings.qalcBinary || !root.backendChecked)
      root.startBackendCheck()
  }

  function loadHistory(raw) {
    if (root.settings.historyMode !== "persistent") {
      root.history = []
      return
    }
    root.history = CalcModel.parseHistory(raw, root.settings.historyLimit,
      root.settings.historyRetentionDays)
  }

  function saveHistory() {
    if (root.settings.historyMode !== "persistent" || !root.storageReady) return
    historyFile.setText(JSON.stringify(root.history, null, 2) + "\n")
  }

  function addCurrentToHistory() {
    // Selected text is intentionally session-only and never written to history.
    if (root.transformActive) return
    if (root.settings.historyMode === "disabled" || !root.expression.trim() || !root.result) return
    root.history = CalcModel.addHistoryEntry(root.history, {
      expression: root.expression.trim(),
      result: root.result,
      rawResult: root.rawResult,
      kind: root.resultKind,
      dynamic: root.resultDynamic,
      timestamp: Date.now()
    }, root.settings.historyLimit)
    root.saveHistory()
  }

  function removeSelectedHistory() {
    if (root.selectedHistoryIndex < 0 || root.selectedHistoryIndex >= root.displayHistory.length) return
    var historyIndex = root.displayHistory[root.selectedHistoryIndex].historyIndex
    root.history = CalcModel.removeHistoryEntry(root.history, historyIndex)
    root.saveHistory()
    if (root.displayHistory.length === 0) {
      root.historyOpen = false
      root.selectedHistoryIndex = -1
    } else {
      root.selectedHistoryIndex = Math.min(root.selectedHistoryIndex, root.displayHistory.length - 1)
      historyList.positionViewAtIndex(root.selectedHistoryIndex, ListView.Contain)
    }
  }

  function toggleSelectedHistoryPin() {
    if (root.selectedHistoryIndex < 0 || root.selectedHistoryIndex >= root.displayHistory.length) return
    var historyIndex = root.displayHistory[root.selectedHistoryIndex].historyIndex
    root.history = CalcModel.toggleHistoryPin(root.history, historyIndex)
    root.saveHistory()
    root.selectedHistoryIndex = Math.min(root.selectedHistoryIndex,
      Math.max(0, root.displayHistory.length - 1))
  }

  function requestClearHistory() {
    if (root.history.length === 0) return
    clearConfirm.selectedIndex = 1
    root.clearConfirmOpen = true
  }

  function confirmClearHistory() {
    root.history = []
    root.saveHistory()
    root.clearConfirmOpen = false
    root.historyOpen = false
    root.selectedHistoryIndex = -1
    expressionInput.forceActiveFocus()
  }

  function toggleHistory() {
    if (root.settings.historyMode === "disabled") {
      root.statusText = "History is disabled in config.json"
      return
    }
    root.detailOpen = false
    root.actionMenuOpen = false
    root.historyOpen = !root.historyOpen
    root.historyQuery = ""
    root.selectedHistoryIndex = root.historyOpen && root.displayHistory.length > 0 ? 0 : -1
    if (root.historyOpen && root.selectedHistoryIndex >= 0)
      historyList.positionViewAtIndex(root.selectedHistoryIndex, ListView.Beginning)
    if (root.historyOpen) {
      root.refreshDynamicHistory()
      Qt.callLater(function() { historySearchInput.forceActiveFocus() })
    } else Qt.callLater(function() { expressionInput.forceActiveFocus() })
  }

  function moveHistorySelection(delta) {
    if (!root.historyOpen) {
      root.toggleHistory()
      return
    }
    if (root.displayHistory.length === 0) return
    root.selectedHistoryIndex = Math.max(0, Math.min(root.displayHistory.length - 1,
      root.selectedHistoryIndex + delta))
    historyList.positionViewAtIndex(root.selectedHistoryIndex, ListView.Contain)
  }

  function recallSelectedHistory() {
    if (root.selectedHistoryIndex < 0 || root.selectedHistoryIndex >= root.displayHistory.length) return
    var entry = root.displayHistory[root.selectedHistoryIndex]
    root.historyOpen = false
    root.historyQuery = ""
    root.detailOpen = false
    root.expression = entry.expression
    Qt.callLater(function() {
      expressionInput.forceActiveFocus()
      expressionInput.selectAll()
    })
  }

  function toggleDetail() {
    if (!root.result && !root.errorText) return
    root.historyOpen = false
    root.actionMenuOpen = false
    root.detailOpen = !root.detailOpen
  }

  function scheduleEvaluation() {
    root.pendingAction = ""
    root.evaluationGeneration += 1
    root.pendingExpression = root.calculationExpression()
    root.pendingTimeoutMs = root.settings.previewTimeoutMs
    root.result = ""
    root.clearResultMetadata()
    root.errorText = ""
    root.statusText = ""
    root.detailOpen = false
    evaluationTimer.restart()
  }

  function requestImmediateEvaluation(action) {
    evaluationTimer.stop()
    root.evaluationGeneration += 1
    root.pendingExpression = root.calculationExpression()
    root.pendingTimeoutMs = root.settings.submitTimeoutMs
    root.pendingAction = action
    root.result = ""
    root.clearResultMetadata()
    root.errorText = ""
    root.statusText = ""
    root.startEvaluation()
  }

  function startEvaluation() {
    if (!root.pendingExpression) {
      root.result = ""
      root.errorText = ""
      root.statusText = ""
      return
    }
    if (!root.backendChecked || !root.backendAvailable) return

    if (evaluationProcess.running || !root.activeProcessExited
        || !root.activeStdoutFinished || !root.activeStderrFinished) {
      root.rerunPending = true
      return
    }

    root.rerunPending = false
    root.activeGeneration = root.evaluationGeneration
    root.activeExpression = root.pendingExpression
    root.activeAction = root.pendingAction
    root.activeOutput = ""
    root.activeErrorOutput = ""
    root.activeExitCode = -1
    root.activeProcessExited = false
    root.activeStdoutFinished = false
    root.activeStderrFinished = false
    root.statusText = "Calculating…"

    evaluationProcess.command = root.backendArguments("evaluate").concat([
      "--expression", root.activeExpression,
      "--timeout-ms", String(root.pendingTimeoutMs)
    ])
    evaluationProcess.running = true
  }

  function backendArguments(mode) {
    return [
      "python3", root.backendPath, mode,
      "--qalc", root.settings.qalcBinary,
      "--unicode", root.settings.unicode ? "1" : "0",
      "--digit-grouping", String(root.settings.digitGrouping),
      "--precision", String(root.settings.precision),
      "--clock-format", root.settings.clockFormat,
      "--default-from", root.settings.defaultFromCurrency,
      "--default-to", root.settings.defaultToCurrency,
      "--rate-stale-days", String(root.settings.rateStaleDays),
      "--rem-px", String(root.settings.remPx),
      "--workday-hours", String(root.settings.workdayHours)
    ]
  }

  function finishEvaluationIfReady() {
    if (!root.activeProcessExited || !root.activeStdoutFinished || !root.activeStderrFinished) return

    var isCurrent = root.activeGeneration === root.evaluationGeneration
      && root.activeExpression === root.calculationExpression()

    if (isCurrent) {
      var nextResult = root.normalizeOutput(root.activeOutput)
      var nextError = root.normalizeOutput(root.activeErrorOutput)
      var payload = ({})
      try { payload = JSON.parse(nextResult || "{}") } catch (error) { payload = ({}) }

      if (payload.ok && payload.result) {
        root.result = String(payload.result)
        root.rawResult = String(payload.rawResult || payload.result)
        root.resultKind = String(payload.kind || "math")
        root.normalizedExpression = String(payload.normalizedExpression || root.activeExpression)
        root.swapExpression = String(payload.swapExpression || "")
        root.resultDynamic = Boolean(payload.dynamic)
        root.resultColor = String(payload.colorHex || "")
        root.resultFormats = Array.isArray(payload.formats) ? payload.formats : []
        root.rateDate = String(payload.rateDate || "")
        root.rateSource = String(payload.rateSource || "")
        root.rateAgeDays = Number(payload.rateAgeDays === undefined ? -1 : payload.rateAgeDays)
        root.rateStale = Boolean(payload.rateStale)
        root.errorText = ""
        root.statusText = ""
        root.rebuildActionItems()
        if (root.activeAction) root.completeAction(root.activeAction)
      } else {
        root.result = ""
        root.clearResultMetadata()
        if (root.activeExitCode === 124) root.errorText = "Calculation timed out"
        else root.errorText = String(payload.error || nextError || "No result")
        root.statusText = ""
      }
    }

    root.activeAction = ""
    if (root.activeGeneration !== root.evaluationGeneration || root.rerunPending) {
      root.rerunPending = false
      Qt.callLater(function() { root.startEvaluation() })
    }
  }

  function submit(action) {
    var requestedAction = action || root.settings.defaultAction
    if (!root.backendChecked) return
    if (!root.backendAvailable) {
      root.requestDependencyInstall()
      return
    }
    if (!root.calculationExpression()) {
      root.dismiss()
      return
    }
    if (root.result) {
      root.completeAction(requestedAction)
      return
    }
    root.requestImmediateEvaluation(requestedAction)
  }

  function completeAction(action) {
    if (!root.result) return
    root.addCurrentToHistory()

    if (action === "replace-selection") {
      root.replaceSelection()
      return
    }

    if (action === "reuse") {
      var reused = root.rawResult || root.result
      root.actionMenuOpen = false
      root.expression = reused
      root.statusText = "Result reused"
      Qt.callLater(function() {
        expressionInput.forceActiveFocus()
        expressionInput.selectAll()
      })
      return
    }

    if (action === "copy-equation") {
      root.copyEquation()
      return
    }

    root.copyResult(action === "copy-stay")
  }

  function copyResult(keepOpen) {
    // Capture the evaluated value before dismiss() clears the component state.
    var evaluatedResult = root.result
    if (!evaluatedResult) return
    root.queueCopy(evaluatedResult, keepOpen)
  }

  function copyText(value, keepOpen) {
    var copied = String(value || "")
    if (!copied) return
    root.queueCopy(copied, keepOpen)
  }

  function queueCopy(value, keepOpen) {
    if (!root.clipboardChecked || !root.clipboardAvailable) {
      root.statusText = "Clipboard support is unavailable"
      if (root.clipboardChecked) root.requestDependencyInstall()
      else root.startBackendCheck()
      return
    }
    if (copyProcess.running) return
    root.copyCloseAfter = !keepOpen
    root.copyProcessStarted = true
    root.actionMenuOpen = false
    root.statusText = "Copying…"
    copyProcess.command = ["wl-copy", "--", String(value)]
    copyProcess.running = true
  }

  function copyEquation() {
    if (!root.result) return
    root.queueCopy(root.calculationExpression() + " = " + root.result, false)
  }

  function replaceSelection() {
    if (!root.transformActive || !root.result || !root.transformOriginWindow
        || root.transformOriginPid <= 0) return
    if (!root.clipboardChecked || !root.clipboardAvailable) {
      root.statusText = "Clipboard support is unavailable"
      if (root.clipboardChecked) root.requestDependencyInstall()
      else root.startBackendCheck()
      return
    }
    if (replaceProcess.running) return
    root.replaceProcessStarted = true
    replaceProcess.command = [
      "python3", root.transformHelperPath, "replace",
      "--window-address", root.transformOriginWindow,
      "--window-pid", String(root.transformOriginPid),
      "--result=" + String(root.result)
    ]
    if (root.transformOriginTerminal) replaceProcess.command.push("--terminal")
    replaceProcess.running = true
    Qt.callLater(function() { root.dismiss() })
  }

  function rebuildActionItems() {
    var items = [
      { id: "copy", label: "Copy Answer", value: root.result, enabled: root.clipboardAvailable },
      { id: "copy-raw", label: "Copy Unformatted", value: root.rawResult || root.result, enabled: root.clipboardAvailable },
      { id: "copy-equation", label: "Copy Question & Answer", value: "", enabled: root.clipboardAvailable },
      { id: "reuse", label: "Use Answer as Input", value: "", enabled: true }
    ]
    if (root.transformActive)
      items.splice(1, 0, { id: "replace-selection", label: "Replace Selection", value: "",
        enabled: root.clipboardAvailable })
    if (root.swapExpression)
      items.push({ id: "swap", label: "Swap Units", value: root.swapExpression, enabled: true })
    if (root.resultKind === "currency")
      items.push({ id: "refresh-currency", label: "Refresh Currency Rates", value: root.rateDate, enabled: true })
    for (var index = 0; index < root.resultFormats.length; index += 1) {
      var format = root.resultFormats[index]
      items.push({ id: "format", label: "Copy " + String(format.label), value: String(format.value),
        enabled: root.clipboardAvailable })
    }
    root.actionItems = items
  }

  function toggleActionMenu() {
    if (!root.result) return
    root.historyOpen = false
    root.detailOpen = false
    root.actionMenuOpen = !root.actionMenuOpen
    root.rebuildActionItems()
    root.selectedActionIndex = 0
  }

  function moveActionSelection(delta) {
    if (!root.actionMenuOpen || root.actionItems.length === 0) return
    root.selectedActionIndex = Math.max(0, Math.min(root.actionItems.length - 1,
      root.selectedActionIndex + delta))
    actionList.positionViewAtIndex(root.selectedActionIndex, ListView.Contain)
  }

  function executeSelectedAction() {
    if (root.selectedActionIndex < 0 || root.selectedActionIndex >= root.actionItems.length) return
    var action = root.actionItems[root.selectedActionIndex]
    if (action.enabled === false) {
      root.actionMenuOpen = false
      root.statusText = "Clipboard support is unavailable"
      root.requestDependencyInstall()
      return
    }
    if (action.id === "copy") root.copyText(root.result, false)
    else if (action.id === "replace-selection") root.completeAction("replace-selection")
    else if (action.id === "copy-raw" || action.id === "format") root.copyText(action.value, false)
    else if (action.id === "copy-equation") {
      root.copyText(root.calculationExpression() + " = " + root.result, false)
    } else if (action.id === "reuse") root.completeAction("reuse")
    else if (action.id === "swap") {
      root.actionMenuOpen = false
      root.expression = action.value
      Qt.callLater(function() { expressionInput.forceActiveFocus(); expressionInput.selectAll() })
    } else if (action.id === "refresh-currency") {
      root.actionMenuOpen = false
      root.exchangeRefreshForResult = true
      root.rateStatusOverride = "Refreshing currency rates…"
      root.statusText = "Refreshing currency rates…"
      if (!exchangeRefresh.running) {
        exchangeRefresh.command = [root.settings.qalcBinary, "--exrates"]
        exchangeRefresh.running = true
      }
    }
  }

  function refreshDynamicHistory() {
    if (historyRefresh.running || !root.backendAvailable) return
    var expressions = []
    for (var index = 0; index < root.history.length && expressions.length < 50; index += 1) {
      if (root.history[index].dynamic) expressions.push(root.history[index].expression)
    }
    if (expressions.length === 0) return
    historyRefresh.command = root.backendArguments("batch").concat([
      "--expressions", JSON.stringify(expressions),
      "--timeout-ms", String(root.settings.submitTimeoutMs)
    ])
    historyRefresh.running = true
  }

  function applyHistoryRefresh(raw) {
    var updates = []
    try { updates = JSON.parse(String(raw || "[]")) } catch (error) { return }
    if (!Array.isArray(updates)) return
    var byExpression = ({})
    for (var index = 0; index < updates.length; index += 1)
      if (updates[index].ok) byExpression[String(updates[index].expression)] = updates[index]
    var changed = false
    var next = root.history.slice()
    for (var historyIndex = 0; historyIndex < next.length; historyIndex += 1) {
      var update = byExpression[next[historyIndex].expression]
      if (!update || String(update.result) === next[historyIndex].result) continue
      var entry = ({})
      for (var key in next[historyIndex]) entry[key] = next[historyIndex][key]
      entry.result = String(update.result)
      entry.rawResult = String(update.rawResult || update.result)
      entry.kind = String(update.kind || entry.kind)
      entry.dynamic = Boolean(update.dynamic)
      next[historyIndex] = entry
      changed = true
    }
    if (changed) {
      root.history = next
      root.saveHistory()
    }
  }

  function handleEscape() {
    if (root.clearConfirmOpen) {
      root.clearConfirmOpen = false
    } else if (root.actionMenuOpen) {
      root.actionMenuOpen = false
    } else if (root.detailOpen) {
      root.detailOpen = false
    } else if (root.historyOpen) {
      root.historyOpen = false
      root.historyQuery = ""
      expressionInput.forceActiveFocus()
    } else if (root.expression) {
      root.expression = ""
      expressionInput.forceActiveFocus()
    } else {
      root.dismiss()
    }
  }

  function startBackendCheck() {
    if (backendCheck.running || pythonCheck.running || clipboardCheck.running) return
    root.backendChecked = false
    root.backendAvailable = false
    root.qalcChecked = false
    root.qalcAvailable = false
    root.pythonChecked = false
    root.pythonAvailable = false
    root.clipboardChecked = false
    root.clipboardAvailable = false
    root.backendCheckStarted = true
    root.pythonCheckStarted = true
    root.clipboardCheckStarted = true
    backendCheck.command = [root.settings.qalcBinary, "--version"]
    pythonCheck.command = ["python3", "--version"]
    clipboardCheck.command = ["wl-copy", "--version"]
    backendCheck.running = true
    pythonCheck.running = true
    clipboardCheck.running = true
  }

  function finishBackendCheck(available) {
    if (!root.backendCheckStarted || root.qalcChecked) return
    root.backendCheckStarted = false
    root.qalcAvailable = available
    root.qalcChecked = true
    root.updateDependencyState()
  }

  function finishPythonCheck(available) {
    if (!root.pythonCheckStarted || root.pythonChecked) return
    root.pythonCheckStarted = false
    root.pythonAvailable = available
    root.pythonChecked = true
    root.updateDependencyState()
  }

  function finishClipboardCheck(available) {
    if (!root.clipboardCheckStarted || root.clipboardChecked) return
    root.clipboardCheckStarted = false
    root.clipboardAvailable = available
    root.clipboardChecked = true
    if (root.result) root.rebuildActionItems()
    root.updateDependencyState()
  }

  function updateDependencyState() {
    if (!root.qalcChecked || !root.pythonChecked) return
    var available = root.qalcAvailable && root.pythonAvailable
    root.backendAvailable = available
    root.backendChecked = true

    if (available) {
      if (!root.installRequested || (root.clipboardChecked && root.clipboardAvailable)) {
        root.installRequested = false
        installerPoll.stop()
      }
      if (root.settings.refreshExchangeRates && !root.exchangeRefreshStarted) {
        root.exchangeRefreshStarted = true
        exchangeRefresh.command = [
          root.settings.qalcBinary,
          "--terse",
          "--set", "color off",
          "--set", "save config off",
          "--set", "save definitions off",
          "--set", "update_exchange_rates 1days",
          "--", "1"
        ]
        exchangeRefresh.running = true
      }
      if (root.pendingExpression) root.startEvaluation()
    }
  }

  function requestDependencyInstall() {
    if (!root.qalcAvailable && root.settings.qalcBinary !== "qalc") {
      root.statusText = "Set a valid qalcBinary in " + root.configPath
      return
    }
    if (root.installRequested) return
    root.installRequested = true
    Quickshell.execDetached([
      "omarchy-launch-terminal",
      "bash", "-lc",
      "omarchy pkg add libqalculate wl-clipboard python; status=$?; "
        + "if [ $status -eq 0 ]; then printf '\\nOmaQuickCalc dependencies installed.\\n'; "
        + "else printf '\\nDependency installation failed.\\n'; fi; "
        + "printf 'Press Enter to close this terminal...'; read -r; exit $status"
    ])
    installerPoll.start()
  }

  function handleInputKey(event) {
    if (root.clearConfirmOpen && clearConfirm.handleKey(event)) return true

    var control = (event.modifiers & Qt.ControlModifier) !== 0
    var shift = (event.modifiers & Qt.ShiftModifier) !== 0
    var alt = (event.modifiers & Qt.AltModifier) !== 0

    if (event.key === Qt.Key_Escape) {
      root.handleEscape()
      return true
    }
    if (control && shift && event.key === Qt.Key_Delete) {
      root.requestClearHistory()
      return true
    }
    if (control && event.key === Qt.Key_K) {
      root.toggleActionMenu()
      return true
    }
    if (event.key === Qt.Key_Up) {
      if (root.actionMenuOpen) root.moveActionSelection(-1)
      else root.moveHistorySelection(root.historyOpen ? -1 : 0)
      return true
    }
    if (event.key === Qt.Key_Down && (root.historyOpen || root.actionMenuOpen)) {
      if (root.actionMenuOpen) root.moveActionSelection(1)
      else root.moveHistorySelection(1)
      return true
    }
    if (event.key === Qt.Key_Delete && root.historyOpen) {
      root.removeSelectedHistory()
      return true
    }
    if (control && event.key === Qt.Key_P && root.historyOpen) {
      root.toggleSelectedHistoryPin()
      return true
    }
    if (control && event.key === Qt.Key_H) {
      root.toggleHistory()
      return true
    }
    if (event.key === Qt.Key_Tab && !shift) {
      root.submit("reuse")
      return true
    }
    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      if (root.actionMenuOpen) root.executeSelectedAction()
      else if (root.historyOpen) root.recallSelectedHistory()
      else if (alt) root.toggleDetail()
      else if (shift && root.transformActive) root.submit("replace-selection")
      else if (shift) root.submit("copy-equation")
      else if (control) root.submit("copy-stay")
      else root.submit("")
      return true
    }
    if (control && event.key === Qt.Key_U) {
      root.expression = ""
      return true
    }
    if (control && event.key === Qt.Key_L) {
      expressionInput.selectAll()
      return true
    }
    return false
  }

  Component.onCompleted: initStorage.running = true

  Timer {
    id: evaluationTimer
    interval: 80
    repeat: false
    onTriggered: root.startEvaluation()
  }

  Timer {
    id: installerPoll
    interval: 2000
    repeat: true
    onTriggered: root.startBackendCheck()
  }

  FileView {
    id: configFile
    path: root.configPath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: root.loadSettings(text())
    onLoadFailed: root.loadSettings("")
    onFileChanged: reload()
  }

  FileView {
    id: historyFile
    path: root.historyPath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: root.loadHistory(text())
    onLoadFailed: root.loadHistory("[]")
    onFileChanged: reload()
  }

  FileView {
    id: launchStateFile
    path: root.launchStatePath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: root.loadLaunchState(text())
    onLoadFailed: root.loadLaunchState("{}")
    onFileChanged: reload()
  }

  FileView {
    id: launcherFile
    path: root.launcherPath
    watchChanges: true
    atomicWrites: true
    printErrors: false
    onLoaded: root.ensureLauncher(text())
    onLoadFailed: root.ensureLauncher("")
    onFileChanged: reload()
  }

  Process {
    id: initStorage
    command: ["mkdir", "-p", root.dataDir, root.configDir, root.dataHome + "/applications"]
    onExited: {
      root.storageReady = true
      configFile.reload()
      historyFile.reload()
      launchStateFile.reload()
      launcherFile.reload()
      if (!root.backendChecked) root.startBackendCheck()
    }
  }

  Process {
    id: shortcutStatus
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.setupStatusOutput = text
    }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      Qt.callLater(function() { root.finishShortcutStatus(exitCode) })
    }
  }

  Process {
    id: setupApply
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.setupApplyOutput = text
    }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      Qt.callLater(function() { root.finishSetupApply(exitCode) })
    }
    onRunningChanged: {
      if (!running && root.setupApplyStarted) {
        Qt.callLater(function() {
          if (root.setupApplyStarted) root.finishSetupApply(127)
        })
      }
    }
  }

  Process {
    id: selectionRead
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.transformReadOutput = text
    }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      Qt.callLater(function() { root.finishTransformRead(exitCode) })
    }
    onRunningChanged: {
      if (!running && root.transformReadStarted) {
        Qt.callLater(function() {
          if (root.transformReadStarted) root.finishTransformRead(127)
        })
      }
    }
  }

  Process {
    id: replaceProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: root.replaceProcessStarted = false
    onRunningChanged: {
      if (!running && root.replaceProcessStarted)
        Qt.callLater(function() { root.replaceProcessStarted = false })
    }
  }

  Process {
    id: backendCheck
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) { root.finishBackendCheck(exitCode === 0) }
    onRunningChanged: {
      // Failed process starts do not emit exited(). Let a normal exit win the
      // event-loop race before marking qalc unavailable.
      if (!running && root.backendCheckStarted && !root.qalcChecked) {
        Qt.callLater(function() {
          if (!root.qalcChecked) root.finishBackendCheck(false)
        })
      }
    }
  }

  Process {
    id: pythonCheck
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) { root.finishPythonCheck(exitCode === 0) }
    onRunningChanged: {
      if (!running && root.pythonCheckStarted && !root.pythonChecked) {
        Qt.callLater(function() {
          if (!root.pythonChecked) root.finishPythonCheck(false)
        })
      }
    }
  }

  Process {
    id: clipboardCheck
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) { root.finishClipboardCheck(exitCode === 0) }
    onRunningChanged: {
      if (!running && root.clipboardCheckStarted && !root.clipboardChecked) {
        Qt.callLater(function() {
          if (!root.clipboardChecked) root.finishClipboardCheck(false)
        })
      }
    }
  }

  Process {
    id: copyProcess
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      if (!root.copyProcessStarted) return
      root.copyProcessStarted = false
      if (exitCode === 0) {
        root.clipboardAvailable = true
        root.clipboardChecked = true
        if (root.copyCloseAfter) root.dismiss()
        else {
          root.statusText = "Copied"
          expressionInput.forceActiveFocus()
        }
      } else {
        root.clipboardAvailable = false
        root.clipboardChecked = true
        root.statusText = "Copy failed · install wl-clipboard"
        root.rebuildActionItems()
      }
    }
    onRunningChanged: {
      if (!running && root.copyProcessStarted) {
        Qt.callLater(function() {
          if (!root.copyProcessStarted) return
          root.copyProcessStarted = false
          root.clipboardAvailable = false
          root.clipboardChecked = true
          root.statusText = "Copy failed · install wl-clipboard"
          root.rebuildActionItems()
        })
      }
    }
  }

  Process {
    id: exchangeRefresh
    stdout: StdioCollector { waitForEnd: true }
    stderr: StdioCollector { waitForEnd: true }
    onExited: function(exitCode) {
      if (root.exchangeRefreshForResult) {
        root.exchangeRefreshForResult = false
        if (exitCode === 0) root.requestImmediateEvaluation("")
        else {
          root.rateStatusOverride = "Refresh failed · cached " + (root.rateDate || "rates")
          root.statusText = "Currency refresh failed"
        }
      }
    }
  }

  Process {
    id: historyRefresh
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.applyHistoryRefresh(text)
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  Process {
    id: evaluationProcess

    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.activeOutput = text
        root.activeStdoutFinished = true
        root.finishEvaluationIfReady()
      }
    }

    stderr: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        root.activeErrorOutput = text
        root.activeStderrFinished = true
        root.finishEvaluationIfReady()
      }
    }

    onExited: function(exitCode) {
      root.activeExitCode = exitCode
      root.activeProcessExited = true
      root.finishEvaluationIfReady()
    }

    onRunningChanged: {
      if (!running && root.activeGeneration >= 0 && !root.activeProcessExited) {
        Qt.callLater(function() {
          if (root.activeProcessExited) return
          root.backendAvailable = false
          root.activeExitCode = 127
          root.activeProcessExited = true
          root.activeStdoutFinished = true
          root.activeStderrFinished = true
          root.activeErrorOutput = "Calculator engine unavailable"
          root.finishEvaluationIfReady()
        })
      }
    }
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omaquickcalc"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle { anchors.fill: parent; color: root.scrim }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    BorderSurface {
      id: card
      width: root.cardWidth
      height: root.cardHeight
      anchors.horizontalCenter: parent.horizontalCenter
      y: Math.max(Style.gapsOut, Math.round((panel.height - height) * 0.24))
      radius: root.cornerRadius
      color: root.cardBackground
      borderSpec: root.borderSpec
      padding: root.contentMargin

      Behavior on height {
        NumberAnimation { duration: 150; easing.type: Easing.OutCubic }
      }

      MouseArea {
        anchors.fill: parent
        onClicked: {
          if (root.setupOpen) setupPane.forceActiveFocus()
          else expressionInput.forceActiveFocus()
        }
      }

      Item {
        id: content
        anchors.fill: parent
        anchors.topMargin: card.contentTopInset
        anchors.rightMargin: card.contentRightInset
        anchors.bottomMargin: card.contentBottomInset
        anchors.leftMargin: card.contentLeftInset

        FocusScope {
          id: setupPane
          anchors.fill: parent
          visible: root.setupOpen
          focus: root.setupOpen
          z: 10

          Keys.onPressed: function(event) {
            if (root.handleSetupKey(event)) event.accepted = true
          }

          Text {
            id: setupTitle
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            text: root.setupTitle
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            font.weight: Font.DemiBold
            elide: Text.ElideRight
          }

          Text {
            id: setupDescription
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: setupTitle.bottom
            anchors.topMargin: Style.space(7)
            text: root.setupDescription
            color: root.foreground
            opacity: 0.58
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            wrapMode: Text.Wrap
          }

          Column {
            id: setupRows
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: setupDescription.bottom
            anchors.topMargin: Style.space(16)
            spacing: Style.space(4)
            visible: root.setupItems.length > 0

            Repeater {
              model: root.setupItems

              delegate: Rectangle {
                id: setupRow
                required property int index
                required property var modelData
                width: setupRows.width
                height: Style.space(56)
                radius: Math.max(3, root.cornerRadius - Style.space(3))
                color: index === root.setupSelectedIndex
                  ? Util.alpha(root.accent, 0.13) : Util.alpha(root.foreground, 0.025)
                border.width: index === root.setupSelectedIndex ? Math.max(1, Style.space(1)) : 0
                border.color: Util.alpha(root.accent, 0.52)
                opacity: setupRow.modelData.enabled === false ? 0.45 : 1

                Text {
                  anchors.left: parent.left
                  anchors.leftMargin: Style.space(14)
                  anchors.right: parent.right
                  anchors.rightMargin: Style.space(14)
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.verticalCenterOffset: -Style.space(9)
                  text: setupRow.modelData.label
                  color: setupRow.index === root.setupSelectedIndex ? root.accent : root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.body
                  font.weight: Font.DemiBold
                  elide: Text.ElideRight
                }

                Text {
                  anchors.left: parent.left
                  anchors.leftMargin: Style.space(14)
                  anchors.right: parent.right
                  anchors.rightMargin: Style.space(14)
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.verticalCenterOffset: Style.space(10)
                  text: setupRow.modelData.detail || ""
                  color: setupRow.modelData.detail === "Available" ? root.accent : root.foreground
                  opacity: setupRow.modelData.detail === "Available" ? 0.82 : 0.48
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  elide: Text.ElideRight
                }

                MouseArea {
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onEntered: root.setupSelectedIndex = setupRow.index
                  onClicked: {
                    setupPane.forceActiveFocus()
                    root.setupSelectedIndex = setupRow.index
                    root.chooseSetupItem(setupRow.index)
                  }
                }
              }
            }
          }

          Text {
            anchors.centerIn: parent
            visible: root.setupPage === "applying"
            text: "Checking Hyprland configuration…"
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
          }

          Text {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            text: root.setupPage === "choices"
              ? "↑↓ select   Enter continue   Escape decide later"
              : "↑↓ select   Enter continue   Escape go back"
            color: root.foreground
            opacity: 0.42
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        Item {
          id: inputRow
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          height: root.rowContentHeight
          visible: !root.setupOpen

          Text {
            id: transformOperandLabel
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            visible: root.transformActive && root.transformOperand.length > 0
            width: visible ? Math.min(inputRow.width * 0.38,
              Math.max(Style.space(90), root.transformOperand.length * Style.font.heading * 0.62)) : 0
            text: root.transformOperand + "  →"
            color: root.accent
            opacity: 0.72
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            elide: Text.ElideRight
          }

          Text {
            anchors.left: transformOperandLabel.visible ? transformOperandLabel.right : parent.left
            anchors.leftMargin: transformOperandLabel.visible ? Style.spacing.md : 0
            anchors.right: outputArea.left
            anchors.rightMargin: Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            visible: root.expression.length === 0
            text: root.transformActive ? "in USD, 20% off, in cm…" : root.settings.inputHint
            color: root.foreground
            opacity: 0.48
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            elide: Text.ElideRight
          }

          TextInput {
            id: expressionInput
            anchors.left: transformOperandLabel.visible ? transformOperandLabel.right : parent.left
            anchors.leftMargin: transformOperandLabel.visible ? Style.spacing.md : 0
            anchors.right: outputArea.left
            anchors.rightMargin: Style.spacing.md
            anchors.verticalCenter: parent.verticalCenter
            height: parent.height
            verticalAlignment: TextInput.AlignVCenter
            clip: true
            text: root.expression
            color: root.foreground
            opacity: root.result.length > 0 ? 0.72 : 1
            selectionColor: Style.selectionFill
            selectedTextColor: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.heading
            cursorVisible: root.opened && activeFocus

            onTextEdited: {
              root.historyOpen = false
              root.actionMenuOpen = false
              root.expression = text
            }
            Keys.onPressed: function(event) {
              if (root.handleInputKey(event)) event.accepted = true
            }
          }

          Item {
            id: outputArea
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: (!root.result && root.visibleStatus)
              ? Math.min(Style.space(310), parent.width * 0.47)
              : 0
            height: parent.height
            visible: width > 0

            Text {
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: root.visibleStatus
              color: root.statusIsError ? root.urgent : root.foreground
              opacity: root.statusIsError ? 1 : 0.5
              font.family: root.fontFamily
              font.pixelSize: root.visibleStatus.length > 32 ? Style.font.title : Style.font.heading
              horizontalAlignment: Text.AlignRight
              elide: Text.ElideLeft
            }

            MouseArea {
              anchors.fill: parent
              enabled: !root.backendAvailable && root.backendChecked
              cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
              onClicked: root.requestDependencyInstall()
            }
          }
        }

        Item {
          id: resultRow
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: inputRow.bottom
          height: root.resultRowHeight
          visible: height > 0 && !root.setupOpen

          Rectangle {
            id: resultDivider
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: Math.max(1, Style.space(1))
            color: root.border
            opacity: 0.62
          }

          Item {
            id: resultContent
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: resultDivider.bottom
            anchors.bottom: parent.bottom
            anchors.topMargin: Style.space(7)

            Rectangle {
              id: resultColorSwatch
              visible: root.resultColor.length > 0
              width: visible ? Style.space(26) : 0
              height: width
              radius: Math.max(2, root.cornerRadius - Style.space(5))
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              color: root.resultColor || "transparent"
              border.width: visible ? 1 : 0
              border.color: root.border
            }

            Text {
              id: copyResultHint
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: root.transformActive ? "⇧↵ Replace" : "↵ Copy"
              color: root.foreground
              opacity: 0.46
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            Text {
              id: rateMetadata
              visible: root.rateSummary.length > 0
              width: visible ? Math.min(implicitWidth, Style.space(220)) : 0
              anchors.right: copyResultHint.left
              anchors.rightMargin: visible ? Style.spacing.md : 0
              anchors.verticalCenter: parent.verticalCenter
              text: root.rateSummary
              color: root.rateStale ? root.urgent : root.foreground
              opacity: root.rateStale ? 0.9 : 0.5
              font.family: root.fontFamily
              font.pixelSize: Style.font.caption
              horizontalAlignment: Text.AlignRight
              elide: Text.ElideLeft
            }

            Text {
              id: resultValue
              anchors.left: resultColorSwatch.visible ? resultColorSwatch.right : parent.left
              anchors.leftMargin: resultColorSwatch.visible ? Style.spacing.md : 0
              anchors.right: rateMetadata.visible ? rateMetadata.left : copyResultHint.left
              anchors.rightMargin: Style.spacing.md
              anchors.verticalCenter: parent.verticalCenter
              text: root.displayResult
              color: root.accent
              font.family: root.fontFamily
              font.pixelSize: root.displayResult.length > 42
                ? Math.round(Style.font.heading * 1.15)
                : Math.round(Style.font.heading * 1.5)
              font.weight: Font.Bold
              horizontalAlignment: Text.AlignLeft
              elide: Text.ElideRight
            }

            MouseArea {
              anchors.fill: parent
              cursorShape: Qt.PointingHandCursor
              onClicked: root.submit("copy-close")
            }
          }
        }

        Item {
          id: historyPane
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: resultRow.bottom
          anchors.topMargin: Style.space(12)
          anchors.bottom: parent.bottom
          visible: root.historyOpen && !root.setupOpen

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: Math.max(1, Style.space(1))
            color: root.border
            opacity: 0.65
          }

          Text {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: Style.space(16)
            visible: root.displayHistory.length === 0
            text: root.historyQuery ? "No matching calculations"
              : (root.settings.historyMode === "session" ? "No calculations this session" : "No calculation history")
            color: root.foreground
            opacity: 0.5
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }

          Rectangle {
            id: historySearch
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: Style.space(8)
            height: Style.space(34)
            radius: Math.max(3, root.cornerRadius - Style.space(4))
            color: Util.alpha(root.foreground, 0.055)

            Text {
              anchors.left: parent.left
              anchors.leftMargin: Style.space(10)
              anchors.verticalCenter: parent.verticalCenter
              visible: root.historyQuery.length === 0
              text: "Search history…"
              color: root.foreground
              opacity: 0.38
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            TextInput {
              id: historySearchInput
              anchors.fill: parent
              anchors.leftMargin: Style.space(10)
              anchors.rightMargin: Style.space(10)
              verticalAlignment: TextInput.AlignVCenter
              text: root.historyQuery
              color: root.foreground
              selectionColor: Style.selectionFill
              selectedTextColor: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
              onTextEdited: {
                root.historyQuery = text
                root.selectedHistoryIndex = root.displayHistory.length > 0 ? 0 : -1
              }
              Keys.onPressed: function(event) {
                if (root.handleInputKey(event)) event.accepted = true
              }
            }
          }

          ListView {
            id: historyList
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: historySearch.bottom
            anchors.topMargin: Style.space(5)
            anchors.bottom: historyHelp.top
            clip: true
            spacing: Style.space(2)
            model: root.displayHistory
            currentIndex: root.selectedHistoryIndex
            visible: root.displayHistory.length > 0

            delegate: Rectangle {
              id: historyRow
              required property int index
              required property var modelData
              width: historyList.width
              height: Style.space(40)
              radius: Math.max(0, root.cornerRadius - Style.space(3))
              color: index === root.selectedHistoryIndex ? Util.alpha(root.accent, 0.13) : "transparent"

              Text {
                id: pinMark
                anchors.left: parent.left
                anchors.leftMargin: Style.space(10)
                anchors.verticalCenter: parent.verticalCenter
                text: historyRow.modelData.pinned ? "◆" : ""
                color: root.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
              }

              Text {
                anchors.left: parent.left
                anchors.leftMargin: historyRow.modelData.pinned ? Style.space(28) : Style.space(10)
                anchors.right: rowResult.left
                anchors.rightMargin: Style.spacing.md
                anchors.verticalCenter: parent.verticalCenter
                text: historyRow.modelData.expression
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
              }

              Text {
                id: rowResult
                width: parent.width * 0.42
                anchors.right: parent.right
                anchors.rightMargin: Style.space(10)
                anchors.verticalCenter: parent.verticalCenter
                text: CalcModel.singleLine(historyRow.modelData.result)
                color: root.accent
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideLeft
              }

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                onEntered: root.selectedHistoryIndex = historyRow.index
                onClicked: {
                  root.selectedHistoryIndex = historyRow.index
                  root.recallSelectedHistory()
                }
              }
            }
          }

          Text {
            id: historyHelp
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            text: "↑↓ select   Enter recall   Ctrl+P pin   Delete remove"
            color: root.foreground
            opacity: 0.42
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        Item {
          id: detailPane
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: resultRow.bottom
          anchors.topMargin: Style.space(12)
          anchors.bottom: parent.bottom
          visible: root.detailOpen && !root.setupOpen

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: Math.max(1, Style.space(1))
            color: root.border
            opacity: 0.65
          }

          Flickable {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: Style.space(12)
            anchors.bottom: detailHelp.top
            anchors.bottomMargin: Style.space(6)
            clip: true
            contentWidth: width
            contentHeight: detailText.implicitHeight

            TextEdit {
              id: detailText
              width: parent.width
              readOnly: true
              selectByMouse: true
              wrapMode: TextEdit.Wrap
              text: root.errorText || (root.result + (root.rateSummary ? "\n\n" + root.rateSummary : ""))
              color: root.errorText ? root.urgent : root.foreground
              selectionColor: Style.selectionFill
              selectedTextColor: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }
          }

          Text {
            id: detailHelp
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            text: root.transformActive
              ? "Alt+Enter collapse   Enter copy result   Shift+Enter replace selection"
              : "Alt+Enter collapse   Enter copy result   Shift+Enter copy equation"
            color: root.foreground
            opacity: 0.42
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        Item {
          id: actionPane
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: resultRow.bottom
          anchors.topMargin: Style.space(12)
          anchors.bottom: parent.bottom
          visible: root.actionMenuOpen && !root.setupOpen

          Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: Math.max(1, Style.space(1))
            color: root.border
            opacity: 0.65
          }

          ListView {
            id: actionList
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: Style.space(7)
            anchors.bottom: actionHelp.top
            clip: true
            spacing: Style.space(2)
            model: root.actionItems
            currentIndex: root.selectedActionIndex

            delegate: Rectangle {
              id: actionRow
              required property int index
              required property var modelData
              width: actionList.width
              height: Style.space(40)
              radius: Math.max(0, root.cornerRadius - Style.space(3))
              color: index === root.selectedActionIndex
                ? Util.alpha(root.accent, 0.13) : "transparent"
              opacity: actionRow.modelData.enabled === false ? 0.46 : 1

              Text {
                anchors.left: parent.left
                anchors.leftMargin: Style.space(10)
                anchors.right: actionValue.left
                anchors.rightMargin: Style.spacing.md
                anchors.verticalCenter: parent.verticalCenter
                text: actionRow.modelData.label
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.body
                elide: Text.ElideRight
              }

              Text {
                id: actionValue
                width: parent.width * 0.42
                anchors.right: parent.right
                anchors.rightMargin: Style.space(10)
                anchors.verticalCenter: parent.verticalCenter
                text: actionRow.modelData.value || ""
                color: root.accent
                opacity: text ? 0.78 : 0
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideLeft
              }

              MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                onEntered: root.selectedActionIndex = actionRow.index
                onClicked: {
                  root.selectedActionIndex = actionRow.index
                  root.executeSelectedAction()
                }
              }
            }
          }

          Text {
            id: actionHelp
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            text: "↑↓ select   Enter run   Escape close actions"
            color: root.foreground
            opacity: 0.42
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            elide: Text.ElideRight
          }
        }

        ConfirmDialog {
          id: clearConfirm
          anchors.fill: parent
          opened: root.clearConfirmOpen
          z: 20
          message: "Delete all OmaQuickCalc history?"
          confirmText: "Delete"
          background: root.cardBackground
          foreground: root.foreground
          scrim: root.scrim
          selectedBackground: Util.alpha(root.accent, 0.13)
          selectedText: root.accent
          fontFamily: root.fontFamily
          cornerRadius: root.cornerRadius
          onCanceled: {
            root.clearConfirmOpen = false
            expressionInput.forceActiveFocus()
          }
          onConfirmed: root.confirmClearHistory()
        }
      }
    }
  }
}
