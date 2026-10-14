#include <QGuiApplication>
#include <QWaylandCompositor>
#include <QWaylandOutput>
#include <QWaylandOutputMode>
#include <QWaylandSeat>
#include <QWaylandSurface>
#include <QWaylandXdgShell>
#include <QMimeData>
#include <QFile>
#include <QTimer>
#include <wayland-server-core.h>
#include "ext-server.h"
#include <atomic>
#include <chrono>
#include <csignal>
#include <fcntl.h>
#include <thread>
#include <unistd.h>
#include <cstdio>

struct State { QString directory; };
struct Offer { State *state; bool primary; };
static void destroyRequest(wl_client *, wl_resource *resource) { wl_resource_destroy(resource); }
static QByteArray mode(State *state) {
 QFile file(state->directory + "/mode");
 if (file.open(QIODevice::ReadOnly)) return file.read(64).trimmed();
 return "small";
}
static QByteArray body(const QByteArray &current) {
 if (current == "oversize") return QByteArray(17 * 1024, 'x');
 if (current == "capacity") return QByteArray(4097, 'x');
 if (current == "appearance") return "64px in rem";
 return "abc";
}
static void receiveOffer(wl_client *, wl_resource *resource, const char *mime, int fd) {
 auto *offer = static_cast<Offer *>(wl_resource_get_user_data(resource));
 auto *state = offer->state;
 auto current = mode(state);
 QFile log(state->directory + "/receives.log");
 if (log.open(QIODevice::Append)) log.write(current + (offer->primary ? " primary " : " clipboard ") + mime + "\n");
 auto payload = body(current);
 fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
 // All test sources are finite. Deadline also covers a client that stops reading.
 std::thread([fd, current, payload]() {
  auto until = std::chrono::steady_clock::now() + std::chrono::seconds(3);
  if (current == "stall") std::this_thread::sleep_for(std::chrono::seconds(2));
  else if (current == "drip") {
   for (int i = 0; i < 50; ++i) {
    if (write(fd, "x", 1) < 0 && errno != EAGAIN) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(40));
   }
  } else {
   if (current == "delayed") std::this_thread::sleep_for(std::chrono::milliseconds(200));
   size_t position = 0;
   while (position < size_t(payload.size()) && std::chrono::steady_clock::now() < until) {
    auto count = write(fd, payload.data() + position, payload.size() - position);
    if (count > 0) position += count;
    else if (errno == EAGAIN) std::this_thread::sleep_for(std::chrono::milliseconds(5));
    else break;
   }
  }
  close(fd);
 }).detach();
}
static const struct ext_data_control_offer_v1_interface offerImpl = {receiveOffer, destroyRequest};
static wl_resource *offer(wl_client *client, wl_resource *device, State *state, bool primary) {
 auto *resource = wl_resource_create(client, &ext_data_control_offer_v1_interface, 1, 0);
 wl_resource_set_implementation(resource, &offerImpl, new Offer{state, primary},
  [](wl_resource *offer) { delete static_cast<Offer *>(wl_resource_get_user_data(offer)); });
 ext_data_control_device_v1_send_data_offer(device, resource);
 ext_data_control_offer_v1_send_offer(resource, "text/plain;charset=utf-8");
 ext_data_control_offer_v1_send_offer(resource, "text/plain");
 return resource;
}
static void fixedSelection(wl_client *, wl_resource *, wl_resource *) {}
static const struct ext_data_control_device_v1_interface deviceImpl = {fixedSelection, destroyRequest, fixedSelection};
static void sourceOffer(wl_client *, wl_resource *, const char *) {}
static const struct ext_data_control_source_v1_interface sourceImpl = {sourceOffer, destroyRequest};
static void createSource(wl_client *client, wl_resource *, uint32_t id) {
 auto *source = wl_resource_create(client, &ext_data_control_source_v1_interface, 1, id);
 wl_resource_set_implementation(source, &sourceImpl, nullptr, nullptr);
}
static void getDevice(wl_client *client, wl_resource *manager, uint32_t id, wl_resource *) {
 auto *state = static_cast<State *>(wl_resource_get_user_data(manager));
 auto *device = wl_resource_create(client, &ext_data_control_device_v1_interface, 1, id);
 wl_resource_set_implementation(device, &deviceImpl, state, nullptr);
 ext_data_control_device_v1_send_selection(device, offer(client, device, state, false));
 ext_data_control_device_v1_send_primary_selection(device, offer(client, device, state, true));
}
static const struct ext_data_control_manager_v1_interface managerImpl = {createSource, getDevice, destroyRequest};
static void bindManager(wl_client *client, void *data, uint32_t version, uint32_t id) {
 auto *resource = wl_resource_create(client, &ext_data_control_manager_v1_interface, qMin(version, 1U), id);
 wl_resource_set_implementation(resource, &managerImpl, data, nullptr);
}
int main(int argc, char **argv) {
 QGuiApplication app(argc, argv);
 if (app.platformName() != "offscreen" || argc != 2) return 2;
 signal(SIGPIPE, SIG_IGN);
 State state{QString::fromLocal8Bit(argv[1])};
 QWaylandCompositor compositor;
 compositor.setSocketName("guarded-test");
 compositor.setUseHardwareIntegrationExtension(false);
 compositor.setRetainedSelectionEnabled(false);
 compositor.create();
 if (!compositor.isCreated()) return 3;
 QWaylandOutput output(&compositor, nullptr);
 output.setSizeFollowsWindow(false);
 QWaylandOutputMode displayMode(QSize(960, 360), 60000);
 output.addMode(displayMode, true); output.setCurrentMode(displayMode);
 compositor.setDefaultOutput(&output);
 QWaylandXdgShell shell(&compositor);
 if (!shell.isInitialized()) shell.initialize();
 auto updateSelection = [&]() {
  QMimeData data; data.setData("text/plain;charset=utf-8", body(mode(&state)));
  data.setData("text/plain", body(mode(&state)));
  compositor.overrideSelection(&data);
 };
 QObject::connect(&shell, &QWaylandXdgShell::toplevelCreated, &app,
  [&](QWaylandXdgToplevel *top, QWaylandXdgSurface *surface) {
   top->sendConfigure(QSize(960, 360), QList<QWaylandXdgToplevel::State>{QWaylandXdgToplevel::ActivatedState});
   compositor.defaultSeat()->setKeyboardFocus(surface->surface());
   QTimer::singleShot(150, &app, updateSelection);
  });
 wl_global_create(compositor.display(), &ext_data_control_manager_v1_interface, 1, &state, bindManager);
 QTimer frame;
 QObject::connect(&frame, &QTimer::timeout, &app, [&]() {
  for (auto *surface : compositor.surfaces()) { surface->frameStarted(); surface->sendFrameCallbacks(); }
 });
 frame.start(16);
 QByteArray previous;
 QTimer selection;
 QObject::connect(&selection, &QTimer::timeout, &app, [&]() {
  auto current = mode(&state); if (current != previous) { previous = current; updateSelection(); }
 });
 selection.start(30);
 QTimer::singleShot(20000, &app, &QCoreApplication::quit);
 std::puts("DISPOSABLE_COMPOSITOR_READY"); std::fflush(stdout);
 return app.exec();
}
