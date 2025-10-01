import json
import requests
import os

# Configure seu Token de Acesso Pessoal do GitHub aqui
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def get_pull_requests(owner, repo, token, num_pulls=10):
    """
    Busca os 10 últimos pull requests de um repositório.
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
    # Lê o arquivo de entrada com a lista de repositórios
    input_file = "repositorios.json"
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

        print(f"Coletando 10 últimos pull requests de {owner}/{repo_name}...")
        pull_requests = get_pull_requests(owner, repo_name, GITHUB_TOKEN)

        if pull_requests:
            # Cria o nome do arquivo de saída
            output_file_name = f"{owner}_{repo_name}_pulls.json"
            
            # Salva os dados em um novo arquivo JSON
            with open(output_file_name, 'w', encoding='utf-8') as f:
                json.dump(pull_requests, f, indent=2)
            
            print(f"Dados salvos em {output_file_name}")

if __name__ == "__main__":
    main()