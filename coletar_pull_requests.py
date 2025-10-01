import json
import requests
import os

# Configura o Token de Acesso Pessoal do GitHub a partir da variável de ambiente
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Define o número de pull requests a serem buscados
# O valor padrão é 10, mas pode ser sobrescrito pela variável de ambiente
try:
    NUM_PULLS = int(os.getenv('NUM_PULLS', 10))
except (ValueError, TypeError):
    print("Aviso: A variável de ambiente NUM_PULLS não é um número válido. Usando o padrão de 10.")
    NUM_PULLS = 10

def get_pull_requests(owner, repo, token, num_pulls):
    """
    Busca os últimos pull requests de um repositório.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }
    params = {
        "state": "all",  # 'open', 'closed' ou 'all'
        "per_page": num_pulls,
        "sort": "updated",
        "direction": "desc"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Lança uma exceção para erros HTTP
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar pull requests de {owner}/{repo}: {e}")
        return None

def main():
    """
    Função principal para processar a lista de repositórios.
    """
    # Define o arquivo de entrada baseado na variável de ambiente (do GitHub Actions) ou usa o padrão
    input_file = os.getenv('REPOS_FILE', 'repositorios.json')

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            repositorios = json.load(f)
    except FileNotFoundError:
        print(f"Erro: O arquivo {input_file} não foi encontrado.")
        return
    except json.JSONDecodeError:
        print(f"Erro: O arquivo {input_file} está em um formato JSON inválido.")
        return

    # Certifica-se de que o token do GitHub foi fornecido
    if not GITHUB_TOKEN:
        print("Erro: A variável de ambiente GITHUB_TOKEN não está definida.")
        print("Crie um token no GitHub e defina-o para a variável de ambiente.")
        return

    # Itera sobre cada repositório e coleta os pull requests
    for repo_info in repositorios:
        owner = repo_info.get('owner')
        repo_name = repo_info.get('repo')

        if not owner or not repo_name:
            print("Aviso: Objeto de repositório inválido. Pulando...")
            continue

        print(f"Coletando {NUM_PULLS} últimos pull requests de {owner}/{repo_name}...")
        pull_requests = get_pull_requests(owner, repo_name, GITHUB_TOKEN, NUM_PULLS)

        if pull_requests:
            # Cria o nome do arquivo de saída no formato owner_repo_pulls.json
            output_file_name = f"{owner}_{repo_name}_pulls.json"

            # Salva os dados em um novo arquivo JSON
            with open(output_file_name, 'w', encoding='utf-8') as f:
                json.dump(pull_requests, f, indent=2)

            print(f"Dados salvos em {output_file_name}")

if __name__ == "__main__":
    main()