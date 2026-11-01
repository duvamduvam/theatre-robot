# Enregistreur de démonstration (outil de débrief, lot R4 embryonnaire) : images caméra aux instants
# demandés + trajectoire vérité terrain + /cmd_vel, pendant un scénario.
import json, sys, time
import numpy as np, rclpy
from PIL import Image as PImage
from rclpy.node import Node
from sensor_msgs.msg import Image
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
SHOTS = [float(x) for x in sys.argv[1].split(",")]
DUR = float(sys.argv[2]); OUT = "/tmp/demo_out"
import os; os.makedirs(OUT, exist_ok=True)
class C(Node):
    def __init__(s):
        super().__init__("demo_capture"); s.t0 = time.monotonic(); s.img = None; s.traj = []; s.cmd = 0.0; s.done = set()
        s.create_subscription(Image, "camera/image_raw", lambda m: setattr(s, "img", m), 1)
        s.create_subscription(Twist, "/cmd_vel", lambda m: setattr(s, "cmd", m.linear.x), 1)
        s.create_subscription(Odometry, "/ground_truth/odom", s.odom, 1)
        s.create_timer(0.2, s.tick)
    def odom(s, m):
        t = time.monotonic() - s.t0; p = m.pose.pose.position
        if not s.traj or t - s.traj[-1][0] > 0.25: s.traj.append((round(t, 2), round(p.x, 3), round(p.y, 3), round(s.cmd, 3)))
    def tick(s):
        t = time.monotonic() - s.t0
        for sh in SHOTS:
            if sh not in s.done and t >= sh and s.img is not None:
                m = s.img; a = np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1)[:, :, :3]
                PImage.fromarray(a).save(f"{OUT}/cam_{int(sh):03d}s.png"); s.done.add(sh)
                print(f"shot {sh}s x={s.traj[-1][1] if s.traj else '?'}", flush=True)
        if t >= DUR:
            json.dump(s.traj, open(f"{OUT}/traj.json", "w")); raise SystemExit
rclpy.init(); n = C()
try: rclpy.spin(n)
except SystemExit: pass
print("fin", flush=True)
