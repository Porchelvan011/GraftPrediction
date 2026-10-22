from locust import HttpUser, task, between
import random

class GraftPredictLoadUser(HttpUser):
    """
    Locust Load Test Suite for GraftPredict Backend.
    Simulates clinical users, doctors, and patients interacting concurrently.
    """
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.client.headers = {
            "Content-Type": "application/json",
            "User-Agent": "GraftPredict-LoadTest-100VUs"
        }

    @task(4)
    def test_health_check(self):
        """High frequency lightweight health check probe."""
        self.client.get("/healthz", name="GET /healthz")

    @task(3)
    def test_readiness_probe(self):
        """Database and pool readiness check."""
        self.client.get("/readyz", name="GET /readyz")

    @task(2)
    def test_user_lookup(self):
        """Simulate user search queries."""
        user_id = random.randint(1, 50)
        self.client.get(f"/search/user/{user_id}", name="GET /search/user/[id]")

    @task(2)
    def test_login_endpoint(self):
        """Simulate authenticated access requests."""
        payload = {
            "email": f"load_user_{random.randint(1, 100)}@hospital.org",
            "password": "Password@2026"
        }
        self.client.post("/login", json=payload, name="POST /login")

    @task(1)
    def test_graft_report_calculation(self):
        """Simulate clinical calculation and report creation."""
        payload = {
            "name": f"Patient-{random.randint(1000, 9999)}",
            "age": random.randint(18, 65),
            "gender": random.choice(["Male", "Female"]),
            "affected_side": random.choice(["left knee", "right knee"]),
            "affected_date": "2026-01-15",
            "height": round(random.uniform(155.0, 190.0), 1),
            "weight": round(random.uniform(50.0, 95.0), 1),
            "bmi": 24.2,
            "leg_length": round(random.uniform(75.0, 95.0), 1),
            "thigh_length": round(random.uniform(40.0, 52.0), 1),
            "circumfrence_thigh": round(random.uniform(45.0, 62.0), 1),
            "posterior_st": round(random.uniform(3.5, 6.0), 1),
            "posterior_gracilis": round(random.uniform(2.8, 4.5), 1),
            "lateral_st": round(random.uniform(3.8, 6.2), 1),
            "lateral_gracilis": round(random.uniform(2.9, 4.8), 1)
        }
        self.client.post("/reports", json=payload, name="POST /reports")
