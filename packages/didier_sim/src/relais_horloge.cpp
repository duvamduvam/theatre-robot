// relais_horloge : l'horloge simulée de Gazebo vers ROS, DÉCIMÉE (sim seulement, 21/11).
//
// Pourquoi : le pont ros_gz relayait /clock à chaque pas de physique (1 ms), soit ≈ 954 Hz mesurés.
// Chaque nœud Python en use_sim_time traite ce flux : 38 à 62 % d'un cœur CHACUN, contre ≈ 1 % sans
// horloge simulée (top, sim chantiers au repos, 21/11). Sous charge, un nœud ainsi occupé se fige
// plus de 0,30 s. Le corps sûr se verrouillait alors (capteur_perdu), fumée 2026-11-21-1929 en V-R3.
// La règle et son seuil ne changent pas (décision du 21/11) : c'est la sim qu'on allège.
//
// Ce que fait le nœud : il s'abonne au topic gz /clock par gz-transport, sans DDS et sans Python.
// Il publie /clock côté ROS au plus une fois par période d'horloge SIMULÉE (paramètre frequence_hz,
// 200 par défaut, soit un pas de 5 ms). Le temps publié est celui du pas gz, exact, jamais arrondi.
// La physique reste à 1 ms : seuls les nœuds ROS voient leur horloge avancer par pas de 5 ms.
// Un temps qui RECULE (monde remis à zéro) est publié tout de suite.
//
// Ce nœud EST l'horloge : il tourne à l'horloge murale (use_sim_time faux, imposé par
// monde.launch.py). Figé ou mort, l'horloge simulée s'arrête pour tous ; c'est sûr, comme une pause
// de Gazebo (minuteries arrêtées, aucun verrou n'en naît).
#include <atomic>
#include <cstdint>
#include <memory>
#include <stdexcept>

#include <gz/msgs/clock.pb.h>
#include <gz/transport/Node.hh>
#include <rclcpp/rclcpp.hpp>
#include <rosgraph_msgs/msg/clock.hpp>

namespace
{

constexpr double FREQUENCE_DEFAUT_HZ = 200.0;
constexpr double FREQUENCE_MAX_HZ = 1000.0;   // le pas de physique des mondes (1 ms)

class RelaisHorloge : public rclcpp::Node
{
public:
  RelaisHorloge()
  : rclcpp::Node("relais_horloge")
  {
    const double hz = declare_parameter<double>("frequence_hz", FREQUENCE_DEFAUT_HZ);
    if (!(hz > 0.0 && hz <= FREQUENCE_MAX_HZ)) {
      throw std::invalid_argument("relais_horloge : frequence_hz hors de ]0, 1000]");
    }
    periode_ns_ = static_cast<int64_t>(1e9 / hz + 0.5);
    // FIABLE, profondeur 10 : la QoS du pont ros_gz qu'il remplace. Un éditeur fiable sert aussi
    // les abonnés « best effort » (TimeSource de rclcpp).
    pub_ = create_publisher<rosgraph_msgs::msg::Clock>("/clock", rclcpp::QoS(10).reliable());
    if (!gz_.Subscribe("/clock", &RelaisHorloge::sur_horloge, this)) {
      throw std::runtime_error("relais_horloge : abonnement au topic gz /clock refusé");
    }
    RCLCPP_INFO(get_logger(), "relais /clock gz -> ROS : %.0f Hz d'horloge simulée (pas %.1f ms)",
      hz, periode_ns_ * 1e-6);
  }

private:
  // Fil de gz-transport (≈ 1 kHz) : une comparaison, et une publication par période.
  void sur_horloge(const gz::msgs::Clock & m)
  {
    const int64_t t = static_cast<int64_t>(m.sim().sec()) * 1000000000LL + m.sim().nsec();
    const int64_t precedent = dernier_publie_ns_.load();
    if (precedent >= 0 && t >= precedent && t - precedent < periode_ns_) {
      return;
    }
    dernier_publie_ns_.store(t);
    rosgraph_msgs::msg::Clock msg;
    msg.clock.sec = static_cast<int32_t>(t / 1000000000LL);
    msg.clock.nanosec = static_cast<uint32_t>(t % 1000000000LL);
    pub_->publish(msg);
  }

  rclcpp::Publisher<rosgraph_msgs::msg::Clock>::SharedPtr pub_;
  int64_t periode_ns_{0};
  std::atomic<int64_t> dernier_publie_ns_{-1};
  // DERNIER membre : détruit le premier, il coupe les rappels avant que pub_ ne disparaisse.
  gz::transport::Node gz_;
};

}  // namespace

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RelaisHorloge>());
  rclcpp::shutdown();
  return 0;
}
