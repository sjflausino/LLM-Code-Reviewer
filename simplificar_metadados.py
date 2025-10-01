import json
import os
import re

def main():
    """
    Função principal para criar um arquivo JSON simplificado
    com links essenciais para pull requests, agrupados por repositório,
    no formato de lista de repositórios.
    """
    repos_dict = {}
    
    # Encontra todos os arquivos JSON de pull requests
    pr_files = [f for f in os.listdir('.') if f.endswith('_pulls.json')]
    
    if not pr_files:
        print("Nenhum arquivo JSON de pull requests encontrado. Execute 'coletar_pull_requests.py' primeiro.")
        return
        
    print("Iniciando a simplificação e agrupamento dos metadados...")

    for pr_file in pr_files:
        print(f"Processando arquivo {pr_file}...")
        
        try:
            with open(pr_file, 'r', encoding='utf-8') as f:
                pull_requests = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Erro ao ler {pr_file}: {e}")
            continue
            
        for pr in pull_requests:
            # Garante que os campos base e repo existem antes de tentar acessar
            if 'base' not in pr or 'repo' not in pr['base'] or 'owner' not in pr['base']['repo']:
                print(f"Aviso: PR inválido ou sem dados de repositório, pulando PR #{pr.get('number', 'N/A')}.")
                continue

            owner = pr['base']['repo']['owner']['login']
            repo = pr['base']['repo']['name']
            pr_number = pr['number']
            
            # Chave única para o repositório
            repo_key = f"{owner}/{repo}"

            # Se o repositório ainda não estiver no dicionário, adicione-o
            if repo_key not in repos_dict:
                repos_dict[repo_key] = {
                    "owner": owner,
                    "repo": repo,
                    "url": pr['base']['repo']['html_url'],
                    "pull_requests": []
                }
            
            # Cria o objeto simplificado do Pull Request
            pr_data = {
                "referencia": f"{owner}/{repo}#{pr_number}",
                "link_pr": pr['html_url'],
                "link_diff": pr['diff_url']
            }
            
            repos_dict[repo_key]["pull_requests"].append(pr_data)

    # Converte o dicionário para uma lista de objetos para o formato final
    final_output = list(repos_dict.values())
        
    output_file = "pr_info_simplificado.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
        
    print(f"Dados simplificados de {len(final_output)} repositórios salvos em '{output_file}'.")

if __name__ == "__main__":
    main()
