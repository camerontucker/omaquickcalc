#include <QGuiApplication>
#include <QClipboard>
#include <QMimeData>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickView>
#include <QInputMethodEvent>
#include <QTest>
#include <QDebug>
#include <memory>
#include <cstdio>

struct Counts { int reads = 0; };
class LazyMime final : public QMimeData {
 public:
  explicit LazyMime(Counts &counts): c(counts) {}
  QStringList formats() const override { return {"text/plain", "text/html"}; }
 protected:
  QVariant retrieveData(const QString &, QMetaType) const override {
    ++c.reads;
    return QByteArray("finite test payload");
  }
 private:
  Counts &c;
};
#define CHECK(condition) do { if (!(condition)) { qCritical() << "FAIL" << __LINE__ << #condition; return 1; } } while (false)

int main(int argc, char **argv) {
 QGuiApplication app(argc, argv);
 CHECK(app.platformName() == "offscreen");
 CHECK(argc == 2);
 Counts counts;
 auto *clipboard = QGuiApplication::clipboard();
 clipboard->setMimeData(new LazyMime(counts));
 QQuickView view;
 view.setSource(QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1]) + "/tests/fixtures/guarded_input.qml"));
 CHECK(view.status() == QQuickView::Ready);
 auto *host = view.rootObject();
 auto *field = host->findChild<QQuickItem *>("field");
 CHECK(field);
 auto *editor = field->findChild<QQuickItem *>("guardedEditor");
 CHECK(editor);
 view.show(); view.requestActivate(); field->forceActiveFocus(); QTest::qWait(30);
 CHECK(editor->hasActiveFocus());
 CHECK(editor->property("canPaste").toBool());
 CHECK(counts.reads == 0);
 for (int i = 0; i < 4; ++i) clipboard->setMimeData(new LazyMime(counts));
 CHECK(counts.reads == 0);
 field->setVisible(false);
 clipboard->setMimeData(new LazyMime(counts));
 CHECK(counts.reads == 0);
 field->setVisible(true); field->forceActiveFocus();
 QTest::keyClick(&view, Qt::Key_V, Qt::ControlModifier);
 CHECK(host->property("pasteRequests").toInt() == 1);
 CHECK(counts.reads == 0);
 QTest::keyClick(&view, Qt::Key_Insert, Qt::ShiftModifier);
 CHECK(host->property("pasteRequests").toInt() == 2);
 CHECK(counts.reads == 0);
 QTest::mouseClick(&view, Qt::MiddleButton, Qt::NoModifier, QPoint(8, 8));
 CHECK(host->property("pasteRequests").toInt() == 3);
 CHECK(host->property("lastPrimary").toBool());
 CHECK(counts.reads == 0);
 std::puts("PASS no unsolicited payload reads; Ctrl+V, Shift+Insert and middle-click are guarded");

 field->setProperty("value", ""); field->forceActiveFocus();
 QTest::keyClick(&view, Qt::Key_A); QTest::keyClick(&view, Qt::Key_B);
 CHECK(field->property("value").toString() == "ab");
 QTest::keyClick(&view, Qt::Key_A, Qt::ControlModifier);
 CHECK(field->property("selectedText").toString() == "ab");
 QTest::keyClick(&view, Qt::Key_X);
 CHECK(field->property("value").toString() == "x");
 QTest::keyClick(&view, Qt::Key_Z, Qt::ControlModifier);
 CHECK(field->property("value").toString() == "ab");
 std::puts("PASS native typing, selection replacement and keyboard undo");

 field->setProperty("value", "");
 QInputMethodEvent preedit(QString::fromUtf8("に"), {});
 QCoreApplication::sendEvent(editor, &preedit);
 CHECK(editor->property("preeditText").toString() == QString::fromUtf8("に"));
 CHECK(field->property("value").toString().isEmpty());
 QInputMethodEvent commit;
 commit.setCommitString(QString::fromUtf8("日本"));
 QCoreApplication::sendEvent(editor, &commit);
 CHECK(field->property("value").toString() == QString::fromUtf8("日本"));
 QTest::keyClick(&view, Qt::Key_Z, Qt::ControlModifier);
 CHECK(field->property("value").toString().isEmpty());
 field->setProperty("maximumLength", 2);
 QInputMethodEvent tooLong;
 tooLong.setCommitString(QString::fromUtf8("日本語"));
 QCoreApplication::sendEvent(editor, &tooLong);
 CHECK(field->property("value").toString().size() <= 2);
 CHECK(editor->property("text").toString().size() <= 2);
 CHECK(counts.reads == 0);
 std::puts("PASS native IME preedit/commit, undo and committed-length guard");

 // Positive control proves the lazy provider exposes the reported Qt mechanism.
 QQmlComponent positive(view.engine());
 positive.setData("import QtQuick\nTextInput { maximumLength: 1 }", QUrl());
 std::unique_ptr<QObject> input(positive.create());
 CHECK(input);
 clipboard->setMimeData(new LazyMime(counts));
 CHECK(counts.reads > 0);
 CHECK(input->property("text").toString().isEmpty());
 std::puts("PASS TextInput positive control reads offered payload without paste");
 input.reset();
 clipboard->clear();
 return 0;
}
