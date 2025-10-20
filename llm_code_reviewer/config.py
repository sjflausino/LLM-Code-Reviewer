import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env para desenvolvimento local
load_dotenv()

# Chaves de API
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configurações do Workflow
# O valor padrão é 10, mas pode ser sobrescrito
try:
    NUM_PULLS = int(os.getenv('NUM_PULLS', 10))
except (ValueError, TypeError):
    print("Aviso: A variável de ambiente NUM_PULLS não é um número válido. Usando o padrão de 10.")
    NUM_PULLS = 10

REPOS_FILE = os.getenv('REPOS_FILE', 'repositorios.json')

# Validação das chaves
if not GITHUB_TOKEN:
    raise ValueError("A variável de ambiente GITHUB_TOKEN não está definida.")
if not GEMINI_API_KEY:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não está definida.") 