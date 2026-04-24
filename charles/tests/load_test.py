from locust import HttpUser, task, between


class CharlesUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def health_check(self):
        self.client.get("/health")

    @task
    def metrics(self):
        self.client.get("/metrics", headers={"Authorization": "Bearer admin_token"})  # Mock token

    @task(3)
    def login(self):
        self.client.post("/auth/login", json={"username": "admin", "password": "admin2026"})