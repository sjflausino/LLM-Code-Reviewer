import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env para desenvolvimento local
load_dotenv()

# Chaves de API
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL_NAME = os.getenv('GEMINI_MODEL_NAME', 'gemini-3.1-flash-lite')
GEMINI_TEMPERATURE = os.getenv('GEMINI_TEMPERATURE', 0.2)
GEMINI_REQUEST_TIMEOUT_SECONDS = int(os.getenv('GEMINI_REQUEST_TIMEOUT_SECONDS', 30))

try:
    GEMINI_TEMPERATURE = float(os.getenv('GEMINI_TEMPERATURE', 0.2))
except (ValueError, TypeError):
    print("Aviso: GEMINI_TEMPERATURE inválida. Usando padrão 0.2.")
    GEMINI_TEMPERATURE = 0.2

# Configurações do Workflow
# O valor padrão é 3, mas pode ser sobrescrito
try:
    NUM_PULLS = int(os.getenv('NUM_PULLS', 3))
except (ValueError, TypeError):
    print("Aviso: A variável de ambiente NUM_PULLS não é um número válido. Usando o padrão de 10.")
    NUM_PULLS = 3

REPOS_FILE = os.getenv('REPOS_FILE', 'repositorios.json')

# Validação das chaves
if not GITHUB_TOKEN:
    raise ValueError("A variável de ambiente GITHUB_TOKEN não está definida.")
if not GEMINI_API_KEY:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não está definida.") 