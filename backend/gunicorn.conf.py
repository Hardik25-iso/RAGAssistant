import multiprocessing
import os

bind = "0.0.0.0:8000"
worker_class = "uvicorn.workers.UvicornWorker"
# t3.micro has 2 vCPU / 1 GB RAM: 2 workers keeps memory in check
workers = int(os.getenv("WEB_CONCURRENCY", min(2, multiprocessing.cpu_count())))
timeout = 90  # LLM calls can take a while; ALB idle timeout is set to 120s
graceful_timeout = 30
keepalive = 75  # longer than nothing, shorter than ALB idle timeout
max_requests = 1000  # recycle workers to avoid slow memory growth
max_requests_jitter = 100
accesslog = None  # access lines are written by SecurityHeadersMiddleware
errorlog = "-"
forwarded_allow_ips = "*"  # only Nginx can reach this port (private Docker network)
