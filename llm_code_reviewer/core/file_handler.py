import json
import os

def load_repos(file_path):
    """Carrega a lista de repositórios de um arquivo JSON."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Erro: O arquivo {file_path} não foi encontrado.")
        return []
    except json.JSONDecodeError:
        print(f"Erro: O arquivo {file_path} está em um formato JSON inválido.")
        return []

def save_json(data, file_path):
    """Salva dados em um arquivo JSON."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Dados salvos em {file_path}")

def save_diff(content, file_path):
    """Salva o conteúdo de um diff, criando diretórios se necessário."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Diff salvo em {file_path}")