"""Multi-model AI debate system using Mixture-of-Agents and Expert Panel patterns."""

# Suppress urllib3 NotOpenSSLWarning before anything imports it (Python 3.9 + LibreSSL)
import warnings
warnings.filterwarnings("ignore", message=".*urllib3.*OpenSSL.*")
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
