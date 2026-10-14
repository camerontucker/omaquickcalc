#include <QGuiApplication>
#include <QQuickView>
#include <QQuickItem>
#include <QQmlContext>
#include <QQmlComponent>
#include <QClipboard>
#include <QProcess>
#include <QProcessEnvironment>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QElapsedTimer>
#include <QTest>
#include <cstdio>
#include <memory>

class Broker : public QObject {
 Q_OBJECT
 public:
 QString repo;
 QProcess reader;
 bool busy = false, succeeded = false, lastPrimary = false, transferOk = false;
 int requests = 0;
 QString error;
 Q_INVOKABLE void request(QObject *target, bool primary, int capacity, int serial) {
  if (busy) return;
  busy = true; succeeded = false; transferOk = false; error.clear(); lastPrimary = primary; ++requests;
  auto environment = QProcessEnvironment::systemEnvironment();
  environment.remove("WAYLAND_DEBUG");
  reader.setProcessEnvironment(environment);
  auto connection = std::make_shared<QMetaObject::Connection>();
  *connection = connect(&reader, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), this,
   [this, target, serial, connection](int status, QProcess::ExitStatus) {
    disconnect(*connection);
    auto output = reader.readAllStandardOutput();
    auto payload = QJsonDocument::fromJson(output).object();
    if (status == 0 && output.size() <= 32768 && payload.value("ok").toBool()) {
     transferOk = true;
     QVariant result;
     QMetaObject::invokeMethod(target, "applyPaste", Q_RETURN_ARG(QVariant, result),
      Q_ARG(QVariant, QVariant(payload.value("text").toString())), Q_ARG(QVariant, QVariant(serial)));
     succeeded = result.toBool();
    } else error = payload.value("error").toString();
    busy = false;
   });
  QStringList args{repo + "/omaquickcalc_paste.py", "--max-characters", QString::number(capacity)};
  if (primary) args.append("--primary");
  reader.start("python3", args);
 }
};
#define CHECK(condition) do { if (!(condition)) { std::fprintf(stderr,"FAIL %d: %s\n",__LINE__,#condition); return 1; } } while(false)
static bool waitFor(Broker &broker) {
 QElapsedTimer clock; clock.start();
 while (broker.busy && clock.elapsed() < 2500) QTest::qWait(10);
 return !broker.busy;
}
static void setMode(const QString &directory, const QByteArray &mode) {
 QFile file(directory + "/mode"); if (!file.open(QIODevice::WriteOnly)) qFatal("Unable to set private test mode"); file.write(mode); file.close();
 QTest::qWait(120);
}
static void select(QObject *field, int start, int end) {
 QMetaObject::invokeMethod(field, "select", Q_ARG(QVariant,QVariant(start)), Q_ARG(QVariant,QVariant(end)));
}
int main(int argc, char **argv) {
 QGuiApplication app(argc, argv);
 CHECK(app.platformName() == "wayland");
 CHECK(argc == 4);
 const QString repo = QString::fromLocal8Bit(argv[1]);
 const QString directory = QString::fromLocal8Bit(argv[2]);
 const QString screenshot = QString::fromLocal8Bit(argv[3]);
 CHECK(qgetenv("XDG_RUNTIME_DIR") == directory.toUtf8());
 CHECK(qgetenv("WAYLAND_DISPLAY") == "guarded-test");
 Broker broker; broker.repo = repo;
 QQuickView view;
 view.rootContext()->setContextProperty("testBroker", &broker);
 view.setSource(QUrl::fromLocalFile(repo + "/tests/fixtures/wayland_guarded_input.qml"));
 CHECK(view.status() == QQuickView::Ready);
 auto *host = view.rootObject();
 auto *field = host->findChild<QQuickItem *>("field"); CHECK(field);
 auto *editor = field->findChild<QQuickItem *>("guardedEditor"); CHECK(editor);
 view.show(); view.requestActivate(); field->forceActiveFocus(); QTest::qWait(350);
 CHECK(editor->hasActiveFocus());
 CHECK(editor->property("canPaste").toBool());
 std::puts("NO_UNSOLICITED_READY"); std::fflush(stdout);
 setMode(directory,"small");
 field->setProperty("value","12345"); select(field,1,4);
 QTest::keyClick(&view, Qt::Key_V, Qt::ControlModifier);
 CHECK(waitFor(broker)); CHECK(broker.succeeded);
 CHECK(field->property("value").toString() == "1abc5");
 QTest::keyClick(&view, Qt::Key_Z, Qt::ControlModifier);
 CHECK(field->property("value").toString() == "12345");
 QTest::keyClick(&view, Qt::Key_Z, Qt::ControlModifier | Qt::ShiftModifier);
 CHECK(field->property("value").toString() == "1abc5");
 std::puts("PASS real Wayland paste and atomic undo/redo"); std::fflush(stdout);
 const int requestsBeforePrimary = broker.requests;
 QTest::mouseClick(&view, Qt::MiddleButton, Qt::NoModifier, QPoint(60,125));
 CHECK(broker.requests == requestsBeforePrimary + 1); CHECK(broker.lastPrimary);
 CHECK(waitFor(broker)); CHECK(broker.succeeded);
 std::puts("PASS real Wayland primary-selection paste"); std::fflush(stdout);

 setMode(directory,"oversize");
 field->setProperty("value","12"); field->setProperty("cursorPosition",2);
 QTest::keyClick(&view, Qt::Key_V, Qt::ControlModifier);
 CHECK(waitFor(broker)); CHECK(!broker.succeeded);
 CHECK(broker.error.contains("too large"));
 CHECK(field->property("value").toString() == "12");
 std::puts("PASS oversized finite Wayland offer rejected before insertion"); std::fflush(stdout);

 setMode(directory,"capacity");
 field->setProperty("value","12"); field->setProperty("cursorPosition",2);
 QTest::keyClick(&view, Qt::Key_V, Qt::ControlModifier);
 CHECK(waitFor(broker)); CHECK(!broker.succeeded); CHECK(broker.error.contains("does not fit"));
 CHECK(field->property("value").toString() == "12");
 std::puts("PASS real Wayland input-capacity rejection"); std::fflush(stdout);

 setMode(directory,"delayed");
 field->setProperty("value","12"); field->setProperty("cursorPosition",2);
 QTest::keyClick(&view, Qt::Key_V, Qt::ControlModifier); QTest::keyClick(&view, Qt::Key_3);
 CHECK(waitFor(broker)); CHECK(broker.transferOk); CHECK(!broker.succeeded);
 CHECK(field->property("value").toString() == "123");
 std::puts("PASS real Wayland successful stale paste rejected after typing"); std::fflush(stdout);

 for (const QByteArray mode : {QByteArray("stall"),QByteArray("drip")}) {
  setMode(directory,mode); field->setProperty("value","12"); field->setProperty("cursorPosition",2);
  QElapsedTimer timer; timer.start();
  QTest::keyClick(&view, Qt::Key_V, Qt::ControlModifier);
  QTest::keyClick(&view, Qt::Key_3);
  CHECK(field->property("value").toString() == "123");
  CHECK(waitFor(broker)); CHECK(!broker.succeeded);
  CHECK(broker.error.contains("timed out")); CHECK(timer.elapsed() < 1600);
  CHECK(field->property("value").toString() == "123");
 }
 std::puts("PASS real Wayland stall/drip deadlines and responsive typing"); std::fflush(stdout);

 setMode(directory,"appearance");
 field->setProperty("value","64px in rem"); field->setProperty("cursorPosition",11);
 QProcess evaluator; evaluator.start("python3",{repo+"/omaquickcalc_backend.py","evaluate","--expression","64px in rem"});
 CHECK(evaluator.waitForFinished(2000));
 auto evaluation = QJsonDocument::fromJson(evaluator.readAllStandardOutput()).object();
 CHECK(evaluation.value("ok").toBool());
 host->setProperty("resultText", evaluation.value("result").toString());
 QTest::qWait(200);
 auto image = view.grabWindow(); CHECK(!image.isNull()); CHECK(image.save(screenshot));
 std::puts("PASS actual guarded widget appearance captured with evaluator result"); std::fflush(stdout);

 std::puts("BEGIN_POSITIVE_CONTROL"); std::fflush(stdout);
 QQmlComponent positive(view.engine());
 positive.setData("import QtQuick\nTextInput { maximumLength: 1 }",QUrl());
 std::unique_ptr<QObject> input(positive.create()); CHECK(input);
 QGuiApplication::clipboard()->dataChanged();
 CHECK(input->property("canPaste").toBool()); CHECK(input->property("text").toString().isEmpty());
 std::puts("PASS finite real Wayland TextInput positive control"); std::fflush(stdout);
 input.reset();
 return 0;
}
#include "client.moc"
